"""
backend/app/routers/staff_interventions.py

Feature 34: Staff Intervention Management Router (Component 4 FR10).
Provides:
  - GET /api/v1/staff/interventions: Filterable table of operational intervention records.
  - GET /api/v1/staff/interventions/staff-members: Active staff members for assignment.
  - GET /api/v1/staff/interventions/{intervention_id}: Full intervention detail, notes, and timeline.
  - POST /api/v1/staff/interventions: Manual counselor-initiated intervention.
  - PATCH /api/v1/staff/interventions/{intervention_id}: Update assignment, schedule, or lifecycle.
  - POST /api/v1/staff/interventions/{intervention_id}/notes: Append immutable counselor case note.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.privacy import scrub_text
from app.db import collections as col
from app.db.storage_models import InterventionStorage
from app.models.intervention_record import (
    COL_INTERVENTION_RECORDS,
    InterventionNote,
    InterventionRecord,
    StatusHistoryEntry,
)
from app.models.user import User
from app.routers.export import get_eligible_consenting_pids
from app.schemas.staff_interventions import (
    ManualInterventionCreateRequest,
    StaffInterventionDetailResponse,
    StaffInterventionListItem,
    StaffInterventionListResponse,
    StaffInterventionNoteCreateRequest,
    StaffInterventionNoteCreateResponse,
    StaffInterventionNoteItem,
    StaffInterventionPatchRequest,
    StaffMemberItem,
)
from app.services.intervention_catalog import (
    delivery_module_for,
    get_entry,
    get_label,
    get_student_label,
    is_known,
)
from app.services.intervention_events import on_intervention_offered
from app.services.intervention_service import change_status
from app.services.staff_access import (
    audit_student_view,
    is_pid_visible,
    require_staff,
    validate_pid,
)
from app.services.student_context import get_analytics_snapshot

router = APIRouter(prefix="/api/v1/staff/interventions", tags=["staff-interventions"])

STAFF_ALLOWED_STATUS_TRANSITIONS = {"offered", "in_progress", "cancelled"}


async def _resolve_staff_names(
    db: AsyncIOMotorDatabase,
    user_ids: List[str],
) -> Dict[str, str]:
    """Helper to map user IDs to staff full names in batch."""
    if not user_ids:
        return {}
    clean_ids = [str(uid).strip() for uid in user_ids if uid]
    cursor = db[col.USERS].find(
        {"$or": [{"_id": {"$in": clean_ids}}, {"id": {"$in": clean_ids}}]},
        {"_id": 1, "id": 1, "full_name": 1},
    )
    mapping: Dict[str, str] = {}
    async for u in cursor:
        name = str(u.get("full_name") or "Staff Member")
        if "_id" in u:
            mapping[str(u["_id"])] = name
        if "id" in u:
            mapping[str(u["id"])] = name
    return mapping


# ── GET /api/v1/staff/interventions/staff-members ─────────────────────────────

@router.get(
    "/staff-members",
    response_model=List[StaffMemberItem],
    summary="List active staff members for assignment",
    description="Returns active counsellors and administrators available for intervention case assignment.",
)
async def list_staff_members(
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[StaffMemberItem]:
    cursor = db[col.USERS].find(
        {
            "role": {"$in": ["counsellor", "admin"]},
            "is_active": True,
        },
        {"_id": 1, "id": 1, "full_name": 1, "role": 1},
    )
    members: List[StaffMemberItem] = []
    async for u in cursor:
        uid = str(u.get("_id") or u.get("id"))
        members.append(
            StaffMemberItem(
                id=uid,
                full_name=str(u.get("full_name") or "Staff Member"),
                role=str(u.get("role") or "counsellor"),
            )
        )
    return members


# ── GET /api/v1/staff/interventions ───────────────────────────────────────────

@router.get(
    "",
    response_model=StaffInterventionListResponse,
    summary="List staff intervention records",
    description="Returns filterable list of intervention cases. Filter by status, student PID, assignment, or origin. Consenting students only.",
)
async def list_interventions(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    pid: Optional[str] = Query(None, description="Filter by student pseudonymous PID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned staff member ('me' or user ID)"),
    origin: Optional[str] = Query(None, description="Filter by origin: 'recommendation' or 'manual'"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffInterventionListResponse:
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        await audit_student_view(
            request,
            db,
            current_user,
            pid="cohort",
            view="intervention_list",
        )
        return StaffInterventionListResponse(
            items=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )

    match_filter: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}

    if pid:
        clean_pid = str(pid).strip()
        if clean_pid not in eligible_pids:
            await audit_student_view(
                request,
                db,
                current_user,
                pid=clean_pid,
                view="intervention_list",
            )
            return StaffInterventionListResponse(
                items=[],
                total_count=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )
        match_filter["pid"] = clean_pid

    if status_filter:
        match_filter["status"] = str(status_filter).strip().lower()

    if origin:
        match_filter["origin"] = str(origin).strip().lower()

    if assigned_to:
        if str(assigned_to).strip().lower() == "me":
            match_filter["assigned_to"] = str(current_user.id)
        else:
            match_filter["assigned_to"] = str(assigned_to).strip()

    total_count = await db[COL_INTERVENTION_RECORDS].count_documents(match_filter)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
    skip = (page - 1) * page_size

    cursor = (
        db[COL_INTERVENTION_RECORDS]
        .find(match_filter)
        .sort([("created_at", -1), ("updated_at", -1)])
        .skip(skip)
        .limit(page_size)
    )
    raw_records = await cursor.to_list(length=page_size)

    # Batch resolve staff names
    staff_ids = list({r.get("assigned_to") for r in raw_records if r.get("assigned_to")})
    name_map = await _resolve_staff_names(db, staff_ids)

    items: List[StaffInterventionListItem] = []
    for r in raw_records:
        itype = str(r.get("intervention_type", "academic_support"))
        assignee_id = r.get("assigned_to")
        items.append(
            StaffInterventionListItem(
                id=str(r.get("id") or r.get("_id")),
                recommendation_id=r.get("recommendation_id"),
                origin=str(r.get("origin", "recommendation")),
                pid=str(r["pid"]),
                course_id=str(r.get("course_id", "GENERAL")),
                intervention_type=itype,
                label=get_label(itype),
                student_label=get_student_label(itype),
                delivery_module=delivery_module_for(itype),
                status=str(r.get("status", "approved")),
                created_by=str(r.get("created_by", "system")),
                assigned_to=assignee_id,
                assigned_staff_name=name_map.get(assignee_id) if assignee_id else None,
                scheduled_for=r.get("scheduled_for"),
                created_at=r.get("created_at", datetime.now(timezone.utc)),
                updated_at=r.get("updated_at", datetime.now(timezone.utc)),
            )
        )

    await audit_student_view(
        request,
        db,
        current_user,
        pid=pid or "cohort",
        view="intervention_list",
    )

    return StaffInterventionListResponse(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── GET /api/v1/staff/interventions/{intervention_id} ─────────────────────────

@router.get(
    "/{intervention_id}",
    response_model=StaffInterventionDetailResponse,
    summary="Get full intervention record detail",
    description="Returns detailed intervention record including baseline analytics snapshot, complete status transition timeline, and counselor case notes.",
)
async def get_intervention_detail(
    intervention_id: str,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffInterventionDetailResponse:
    clean_id = str(intervention_id).strip()
    record = await db[COL_INTERVENTION_RECORDS].find_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]}
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    clean_pid = validate_pid(str(record["pid"]))
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    itype = str(record.get("intervention_type", "academic_support"))
    cat_entry = get_entry(itype)

    assignee_id = record.get("assigned_to")
    name_map = await _resolve_staff_names(db, [assignee_id] if assignee_id else [])

    notes_raw = record.get("notes") or []
    formatted_notes: List[StaffInterventionNoteItem] = [
        StaffInterventionNoteItem(
            note_id=str(n.get("note_id") or f"not_{idx}"),
            author_id=str(n.get("author_id", "unknown")),
            author_role=str(n.get("author_role", "staff")),
            content=str(n.get("content", "")),
            created_at=n.get("created_at", datetime.now(timezone.utc)),
        )
        for idx, n in enumerate(notes_raw)
    ]

    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="intervention_detail",
        course_id=record.get("course_id"),
    )

    return StaffInterventionDetailResponse(
        id=str(record.get("id") or record.get("_id")),
        recommendation_id=record.get("recommendation_id"),
        origin=str(record.get("origin", "recommendation")),
        pid=clean_pid,
        course_id=str(record.get("course_id", "GENERAL")),
        intervention_type=itype,
        label=cat_entry["label"],
        student_label=cat_entry["student_label"],
        delivery_module=cat_entry["delivery_module"],
        description=cat_entry["description"],
        status=str(record.get("status", "approved")),
        created_by=str(record.get("created_by", "system")),
        assigned_to=assignee_id,
        assigned_staff_name=name_map.get(assignee_id) if assignee_id else None,
        scheduled_for=record.get("scheduled_for"),
        baseline_snapshot=record.get("baseline_snapshot") or {},
        status_history=record.get("status_history") or [],
        notes=formatted_notes,
        created_at=record.get("created_at", datetime.now(timezone.utc)),
        updated_at=record.get("updated_at", datetime.now(timezone.utc)),
    )


# ── POST /api/v1/staff/interventions ──────────────────────────────────────────

@router.get(
    "/course-check",
    include_in_schema=False,
)
async def check_course():
    return {"status": "ok"}


@router.post(
    "",
    response_model=StaffInterventionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate manual counselor intervention",
    description="Creates a staff-initiated intervention for an enrolled consenting student with captured baseline snapshot and synchronized canonical intervention document.",
)
async def create_manual_intervention(
    payload: ManualInterventionCreateRequest,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffInterventionDetailResponse:
    clean_pid = validate_pid(payload.pid)
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    chosen_type = str(payload.intervention_type).strip().lower()
    if not is_known(chosen_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Intervention type '{chosen_type}' is not recognized in the canonical catalog.",
        )

    cid = str(payload.course_id).strip()
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="course_id is required.",
        )

    now_utc = datetime.now(timezone.utc)
    interv_id = f"int_man_{uuid.uuid4().hex[:10]}"

    # Capture baseline snapshot at creation time
    baseline_snapshot = await get_analytics_snapshot(db, clean_pid, cid)

    # 1. Create canonical interventions document
    canonical_interv = InterventionStorage(
        id=interv_id,
        intervention_id=interv_id,
        recommendation_id=None,
        pid=clean_pid,
        course_id=cid,
        intervention_type=chosen_type,
        status="approved",
        created_at=now_utc,
    )
    await db[col.INTERVENTIONS].insert_one(canonical_interv.model_dump(by_alias=True))

    # 2. Create operational intervention record
    initial_history = StatusHistoryEntry(
        status="approved",
        at=now_utc,
        by=str(current_user.id),
        note=f"Manual intervention initiated by staff: {scrub_text(payload.reason.strip())}",
    )
    operational_record = InterventionRecord(
        id=interv_id,
        recommendation_id=None,
        origin="manual",
        pid=clean_pid,
        course_id=cid,
        intervention_type=chosen_type,
        status="approved",
        created_by=str(current_user.id),
        assigned_to=str(current_user.id),
        scheduled_for=None,
        baseline_snapshot=baseline_snapshot,
        status_history=[initial_history],
        notes=[],
        created_at=now_utc,
        updated_at=now_utc,
    )
    await db[COL_INTERVENTION_RECORDS].insert_one(operational_record.model_dump(by_alias=True))

    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="manual_intervention_create",
        course_id=cid,
    )

    cat_entry = get_entry(chosen_type)
    creator_name = getattr(current_user, "full_name", "Staff Member")

    return StaffInterventionDetailResponse(
        id=interv_id,
        recommendation_id=None,
        origin="manual",
        pid=clean_pid,
        course_id=cid,
        intervention_type=chosen_type,
        label=cat_entry["label"],
        student_label=cat_entry["student_label"],
        delivery_module=cat_entry["delivery_module"],
        description=cat_entry["description"],
        status="approved",
        created_by=str(current_user.id),
        assigned_to=str(current_user.id),
        assigned_staff_name=creator_name,
        scheduled_for=None,
        baseline_snapshot=baseline_snapshot,
        status_history=[initial_history.model_dump()],
        notes=[],
        created_at=now_utc,
        updated_at=now_utc,
    )


# ── PATCH /api/v1/staff/interventions/{intervention_id} ───────────────────────

@router.patch(
    "/{intervention_id}",
    response_model=StaffInterventionDetailResponse,
    summary="Update intervention assignment, schedule, or lifecycle status",
    description="Allows counsellors to assign staff, schedule sessions, and execute allowed lifecycle state transitions (offered, in_progress, cancelled).",
)
async def patch_intervention(
    intervention_id: str,
    payload: StaffInterventionPatchRequest,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffInterventionDetailResponse:
    clean_id = str(intervention_id).strip()
    record = await db[COL_INTERVENTION_RECORDS].find_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]}
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    clean_pid = validate_pid(str(record["pid"]))
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    now_utc = datetime.now(timezone.utc)
    set_fields: Dict[str, Any] = {"updated_at": now_utc}

    # 1. Validate assigned_to if provided
    if payload.assigned_to is not None:
        clean_assignee = str(payload.assigned_to).strip()
        assignee_doc = await db[col.USERS].find_one(
            {
                "$or": [{"_id": clean_assignee}, {"id": clean_assignee}],
                "role": {"$in": ["counsellor", "admin"]},
                "is_active": True,
            }
        )
        if not assignee_doc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Assigned staff ID '{clean_assignee}' must belong to an active counsellor or admin.",
            )
        set_fields["assigned_to"] = clean_assignee

    # 2. Validate scheduled_for if provided
    if payload.scheduled_for is not None:
        sched_dt = payload.scheduled_for
        if sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=timezone.utc)
        else:
            sched_dt = sched_dt.astimezone(timezone.utc)

        # Allow 5 minutes grace window for client time skew
        grace_limit = now_utc - timedelta(minutes=5)
        if sched_dt < grace_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scheduled session datetime cannot be set in the past.",
            )
        set_fields["scheduled_for"] = sched_dt

    # Apply assignment and schedule changes
    if len(set_fields) > 1:
        await db[COL_INTERVENTION_RECORDS].update_one(
            {"$or": [{"id": clean_id}, {"_id": clean_id}]},
            {"$set": set_fields},
        )
        record = await db[COL_INTERVENTION_RECORDS].find_one(
            {"$or": [{"id": clean_id}, {"_id": clean_id}]}
        )

    # 3. Handle lifecycle status transition if requested
    if payload.status is not None:
        requested_status = str(payload.status).strip().lower()
        if requested_status not in STAFF_ALLOWED_STATUS_TRANSITIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Staff patch only permits transitions to {STAFF_ALLOWED_STATUS_TRANSITIONS}. "
                    "'completed' is finalized via outcome evaluation (F35); 'accepted'/'declined' are student decisions (F38)."
                ),
            )

        # Transition status through central service
        record = await change_status(
            db=db,
            record=record,
            new_status=requested_status,
            actor_id=str(current_user.id),
            note=payload.note,
        )

        # Trigger event hook if offered
        if requested_status == "offered":
            try:
                await on_intervention_offered(db, record)
            except Exception as hook_err:
                logger.error("on_intervention_offered hook failed: %s", hook_err)

    # Return refreshed detail response
    itype = str(record.get("intervention_type", "academic_support"))
    cat_entry = get_entry(itype)

    assignee_id = record.get("assigned_to")
    name_map = await _resolve_staff_names(db, [assignee_id] if assignee_id else [])

    notes_raw = record.get("notes") or []
    formatted_notes: List[StaffInterventionNoteItem] = [
        StaffInterventionNoteItem(
            note_id=str(n.get("note_id") or f"not_{idx}"),
            author_id=str(n.get("author_id", "unknown")),
            author_role=str(n.get("author_role", "staff")),
            content=str(n.get("content", "")),
            created_at=n.get("created_at", datetime.now(timezone.utc)),
        )
        for idx, n in enumerate(notes_raw)
    ]

    return StaffInterventionDetailResponse(
        id=str(record.get("id") or record.get("_id")),
        recommendation_id=record.get("recommendation_id"),
        origin=str(record.get("origin", "recommendation")),
        pid=clean_pid,
        course_id=str(record.get("course_id", "GENERAL")),
        intervention_type=itype,
        label=cat_entry["label"],
        student_label=cat_entry["student_label"],
        delivery_module=cat_entry["delivery_module"],
        description=cat_entry["description"],
        status=str(record.get("status", "approved")),
        created_by=str(record.get("created_by", "system")),
        assigned_to=assignee_id,
        assigned_staff_name=name_map.get(assignee_id) if assignee_id else None,
        scheduled_for=record.get("scheduled_for"),
        baseline_snapshot=record.get("baseline_snapshot") or {},
        status_history=record.get("status_history") or [],
        notes=formatted_notes,
        created_at=record.get("created_at", datetime.now(timezone.utc)),
        updated_at=record.get("updated_at", datetime.now(timezone.utc)),
    )


# ── POST /api/v1/staff/interventions/{intervention_id}/notes ──────────────────

@router.post(
    "/{intervention_id}/notes",
    response_model=StaffInterventionNoteCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append counselor case note",
    description="Appends an immutable, privacy-protected counselor case note to the operational record. Notes are never exported or stored in canonical contract collections.",
)
async def add_intervention_note(
    intervention_id: str,
    payload: StaffInterventionNoteCreateRequest,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffInterventionNoteCreateResponse:
    clean_id = str(intervention_id).strip()
    record = await db[COL_INTERVENTION_RECORDS].find_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]}
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    clean_pid = validate_pid(str(record["pid"]))
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    existing_notes = record.get("notes") or []
    if len(existing_notes) >= 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum limit of 50 case notes reached for this intervention record.",
        )

    clean_content = scrub_text(payload.content.strip())
    now_utc = datetime.now(timezone.utc)
    note_id = f"not_{uuid.uuid4().hex[:10]}"

    new_note = InterventionNote(
        note_id=note_id,
        author_id=str(current_user.id),
        author_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        content=clean_content,
        created_at=now_utc,
    )

    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {
            "$push": {"notes": new_note.model_dump()},
            "$set": {"updated_at": now_utc},
        },
    )

    return StaffInterventionNoteCreateResponse(
        note=StaffInterventionNoteItem(
            note_id=new_note.note_id,
            author_id=new_note.author_id,
            author_role=new_note.author_role,
            content=new_note.content,
            created_at=new_note.created_at,
        ),
        total_notes=len(existing_notes) + 1,
    )
