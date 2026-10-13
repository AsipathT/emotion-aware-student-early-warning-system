"""
backend/app/routers/support_staff_mentoring.py

Feature 38-D: Staff Peer Mentoring Router (Component 4 Intervention Delivery).
Prefix: /api/v1/support/mentoring
Tags: ["Support Staff Mentoring"]

Allows academic counsellors and administrators to:
  1. Search active student candidate mentors.
  2. Match an active peer mentor student with an accepted mentee intervention.
  3. Terminate/conclude an active peer mentorship pairing.

Strict Privacy Invariants:
  - Mentee must have accepted the support intervention before any matching is permitted.
  - Mentor receives ONLY mentee's display name and collaborative study purpose.
  - No risk scores, affective indicators, diagnostic labels, or intervention reasons are exposed to the mentor.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.support_mentoring import (
    COL_MENTORING_ASSIGNMENTS,
    MENTORING_STATUS_ACTIVE,
    MENTORING_STATUS_ENDED,
)
from app.models.user import User, UserRole
from app.schemas.staff_mentoring import (
    AssignMentorRequest,
    CandidateListResponse,
    CandidateStudent,
    MentoringAssignmentResponse,
)
from app.services.intervention_catalog import get_entry
from app.services.intervention_service import change_status
from app.services.notification_service import create_notification

logger = logging.getLogger("app.support_staff_mentoring")

router = APIRouter(
    prefix="/api/v1/support/mentoring",
    tags=["Support Staff Mentoring"],
)

STAFF_ROLES = frozenset({UserRole.COUNSELLOR, UserRole.ADMIN})


def _require_staff(user: User) -> None:
    """Enforces that caller holds counsellor or administrator privileges."""
    role = user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))
    if role not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Staff privileges (counsellor or admin) required.",
        )


@router.get(
    "/candidates",
    response_model=CandidateListResponse,
    summary="Search candidate student mentors",
    description="Returns up to 20 active student accounts matching search query. Excludes the mentee if intervention_id is provided.",
)
async def search_candidate_mentors(
    q: Optional[str] = Query(None, description="Search term for student full name"),
    intervention_id: Optional[str] = Query(None, description="Optional intervention ID to exclude the mentee"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CandidateListResponse:
    """Searches active students eligible to serve as peer mentors."""
    _require_staff(current_user)

    exclude_user_ids = []

    # If intervention_id is provided, resolve and exclude the mentee
    if intervention_id:
        clean_interv_id = str(intervention_id).strip()
        rec = await db[COL_INTERVENTION_RECORDS].find_one({
            "$or": [{"id": clean_interv_id}, {"_id": clean_interv_id}]
        })
        if rec and rec.get("pid"):
            mentee_doc = await db.users.find_one({"pid": rec["pid"]})
            if mentee_doc:
                mid = str(mentee_doc.get("_id") or mentee_doc.get("id"))
                exclude_user_ids.append(mid)

    query_filter: dict = {
        "is_active": True,
        "role": UserRole.STUDENT.value,
    }

    if exclude_user_ids:
        query_filter["$and"] = [
            {"_id": {"$nin": exclude_user_ids}},
            {"id": {"$nin": exclude_user_ids}},
        ]

    if q and q.strip():
        query_filter["full_name"] = {"$regex": q.strip(), "$options": "i"}

    cursor = db.users.find(query_filter, {"_id": 1, "id": 1, "full_name": 1}).sort("full_name", 1).limit(20)
    user_docs = await cursor.to_list(length=20)

    items = [
        CandidateStudent(
            id=str(u.get("_id") or u.get("id")),
            full_name=u.get("full_name") or "Student",
        )
        for u in user_docs
    ]

    return CandidateListResponse(items=items, total_count=len(items))


@router.post(
    "/interventions/{intervention_id}",
    response_model=MentoringAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign peer mentor to accepted intervention",
    description="Pairs an active student peer mentor with an accepted mentee intervention. Notifies both students neutrally.",
)
async def assign_peer_mentor(
    intervention_id: str,
    payload: AssignMentorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MentoringAssignmentResponse:
    """
    Pairs an active student peer mentor with an accepted intervention.
    Enforces that:
      1. Intervention delivery module is peer_mentoring.
      2. Mentee has accepted the intervention (status 'accepted' or 'in_progress').
      3. Mentor is an active student and not the mentee.
      4. No active mentor is already assigned (409 conflict).
    """
    _require_staff(current_user)

    clean_interv_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({
        "$or": [{"id": clean_interv_id}, {"_id": clean_interv_id}]
    })
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intervention record not found.",
        )

    # Delivery module check
    catalog_entry = get_entry(rec.get("intervention_type"))
    if catalog_entry.get("delivery_module") != "peer_mentoring":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This intervention does not use the peer_mentoring delivery module.",
        )

    # Privacy Invariant: Intervention must be accepted before matching anyone
    current_status = str(rec.get("status", "")).strip().lower()
    if current_status not in ("accepted", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Peer mentor can only be assigned to accepted or in_progress interventions (current status: '{current_status}').",
        )

    # Resolve mentee user
    student_pid = rec.get("pid")
    mentee_doc = await db.users.find_one({"pid": student_pid})
    if not mentee_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mentee student account not found.",
        )
    mentee_user_id = str(mentee_doc.get("_id") or mentee_doc.get("id"))
    mentee_display_name = mentee_doc.get("full_name") or mentee_doc.get("name") or "Student"

    # Validate mentor
    clean_mentor_id = str(payload.mentor_user_id).strip()
    if clean_mentor_id == mentee_user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mentor cannot be the same student as the mentee.",
        )

    mentor_doc = await db.users.find_one({"$or": [{"_id": clean_mentor_id}, {"id": clean_mentor_id}]})
    if not mentor_doc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected mentor student account not found.",
        )
    if not mentor_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected mentor student account is inactive.",
        )

    mentor_role = str(mentor_doc.get("role", "")).strip().lower()
    if mentor_role != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mentor must be an active student.",
        )
    mentor_display_name = mentor_doc.get("full_name") or mentor_doc.get("name") or "Peer Mentor"

    # Check for active existing assignment
    existing_active = await db[COL_MENTORING_ASSIGNMENTS].find_one({
        "intervention_id": clean_interv_id,
        "status": MENTORING_STATUS_ACTIVE,
    })
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active peer mentor is already assigned to this intervention.",
        )

    now_utc = datetime.now(timezone.utc)
    assignment_id = str(uuid.uuid4())
    assignment_doc = {
        "id": assignment_id,
        "intervention_id": clean_interv_id,
        "mentee_user_id": mentee_user_id,
        "mentor_user_id": clean_mentor_id,
        "status": MENTORING_STATUS_ACTIVE,
        "created_by": str(current_user.id),
        "created_at": now_utc,
        "ended_at": None,
    }
    await db[COL_MENTORING_ASSIGNMENTS].insert_one(assignment_doc)

    # Lifecycle state transition: if currently accepted, advance to in_progress
    if current_status == "accepted":
        try:
            await change_status(
                db=db,
                record=rec,
                new_status="in_progress",
                actor_id=str(current_user.id),
                note=f"Peer mentor matched: {mentor_display_name}",
            )
        except Exception as exc:
            logger.warning("Status transition on mentoring assignment failed: %s", exc)

    # Notify mentee (supportive, names mentor, zero risk labels)
    try:
        await create_notification(
            db=db,
            user_id=mentee_user_id,
            type="mentor_assigned",
            title="Peer Mentorship Connection",
            body=f"You have been matched with peer mentor {mentor_display_name} for collaborative study and academic navigation.",
            link="/messages",
            related_id=clean_interv_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify mentee of mentor match: %s", exc)

    # Notify mentor (neutral wording: names mentee, zero intervention/risk details)
    try:
        await create_notification(
            db=db,
            user_id=clean_mentor_id,
            type="mentor_assigned",
            title="Peer Mentorship Connection",
            body=f"You have been matched as a peer mentor with {mentee_display_name} for collaborative study and academic navigation.",
            link="/messages",
            related_id=assignment_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify mentor of match: %s", exc)

    return MentoringAssignmentResponse(
        id=assignment_id,
        intervention_id=clean_interv_id,
        mentee_user_id=mentee_user_id,
        mentee_name=mentee_display_name,
        mentor_user_id=clean_mentor_id,
        mentor_name=mentor_display_name,
        status=MENTORING_STATUS_ACTIVE,
        created_by=str(current_user.id),
        created_at=now_utc,
        ended_at=None,
    )


@router.get(
    "/interventions/{intervention_id}",
    response_model=Optional[MentoringAssignmentResponse],
    summary="Get mentoring assignment for intervention",
    description="Returns the active or most recent mentoring assignment for this intervention.",
)
async def get_intervention_mentoring_assignment(
    intervention_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Optional[MentoringAssignmentResponse]:
    """Returns current mentoring assignment for staff intervention view."""
    _require_staff(current_user)

    clean_interv_id = str(intervention_id).strip()
    assignment = await db[COL_MENTORING_ASSIGNMENTS].find_one(
        {"intervention_id": clean_interv_id},
        sort=[("created_at", -1)],
    )
    if not assignment:
        return None

    mentor_doc = await db.users.find_one({"$or": [{"_id": assignment["mentor_user_id"]}, {"id": assignment["mentor_user_id"]}]})
    mentee_doc = await db.users.find_one({"$or": [{"_id": assignment["mentee_user_id"]}, {"id": assignment["mentee_user_id"]}]})

    return MentoringAssignmentResponse(
        id=str(assignment.get("id") or assignment.get("_id")),
        intervention_id=clean_interv_id,
        mentee_user_id=str(assignment["mentee_user_id"]),
        mentee_name=mentee_doc.get("full_name") if mentee_doc else "Student",
        mentor_user_id=str(assignment["mentor_user_id"]),
        mentor_name=mentor_doc.get("full_name") if mentor_doc else "Peer Mentor",
        status=assignment.get("status", MENTORING_STATUS_ACTIVE),
        created_by=str(assignment.get("created_by", "")),
        created_at=assignment["created_at"],
        ended_at=assignment.get("ended_at"),
    )


@router.post(
    "/{assignment_id}/end",
    response_model=MentoringAssignmentResponse,
    summary="Conclude mentoring assignment",
    description="Marks an active peer mentorship pairing as ended.",
)
async def end_peer_mentoring_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MentoringAssignmentResponse:
    """Concludes an active peer mentoring assignment."""
    _require_staff(current_user)

    clean_id = str(assignment_id).strip()
    assignment = await db[COL_MENTORING_ASSIGNMENTS].find_one({
        "$or": [{"id": clean_id}, {"_id": clean_id}]
    })
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mentoring assignment not found.",
        )

    now_utc = datetime.now(timezone.utc)
    if assignment.get("status") != MENTORING_STATUS_ENDED:
        await db[COL_MENTORING_ASSIGNMENTS].update_one(
            {"$or": [{"id": clean_id}, {"_id": clean_id}]},
            {"$set": {"status": MENTORING_STATUS_ENDED, "ended_at": now_utc}},
        )
        assignment["status"] = MENTORING_STATUS_ENDED
        assignment["ended_at"] = now_utc

    mentor_doc = await db.users.find_one({"$or": [{"_id": assignment["mentor_user_id"]}, {"id": assignment["mentor_user_id"]}]})
    mentee_doc = await db.users.find_one({"$or": [{"_id": assignment["mentee_user_id"]}, {"id": assignment["mentee_user_id"]}]})

    return MentoringAssignmentResponse(
        id=str(assignment.get("id") or assignment.get("_id")),
        intervention_id=str(assignment["intervention_id"]),
        mentee_user_id=str(assignment["mentee_user_id"]),
        mentee_name=mentee_doc.get("full_name") if mentee_doc else "Student",
        mentor_user_id=str(assignment["mentor_user_id"]),
        mentor_name=mentor_doc.get("full_name") if mentor_doc else "Peer Mentor",
        status=MENTORING_STATUS_ENDED,
        created_by=str(assignment.get("created_by", "")),
        created_at=assignment["created_at"],
        ended_at=assignment.get("ended_at"),
    )
