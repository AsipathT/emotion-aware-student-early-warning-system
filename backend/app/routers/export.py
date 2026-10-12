"""
backend/app/routers/export.py

Feature 21 (Part C): Read-only, secured, paginated, pseudonymized export API
serving LMS -> ML component contract payloads:
  - GET /api/v1/export/messages  -> Component 1 (Affective State Detection)
  - GET /api/v1/export/behavior  -> Component 2 (Behavioral Engagement Trajectory)
  - GET /api/v1/export/academic  -> Component 3 (Multimodal Risk Prediction)

Enforces:
  - Scope authorization via 'X-Component-Key' or Admin Bearer token.
  - Consent filtering: requires active accepted consent for active notice,
    exempting public research data (source == 'oulad').
  - Privacy safety nets: clean_text only, PII scans for email/reg-id patterns.
  - Critical audit logging: AuditAction.EXPORT_GENERATED must succeed before data return.
  - Strict contract envelopes: Envelope[T] with CONTRACT_VERSION.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.academic_derivation import build_academic_record
from app.core.component_auth import ExportActor, export_actor
from app.core.contract_version import CONTRACT_VERSION
from app.core.database import get_db
from app.core.privacy import EMAIL_REGEX, REG_ID_REGEX, is_valid_pid
from app.db import collections as col
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import (
    ComponentSource,
    Decision,
    DistressClass,
    Envelope,
    RiskTier,
    TrajectoryLabel,
)
from app.schemas.contract.v1.c1_affective import AffectiveWeeklyVector, TextMessageRecord, TopDriver
from app.schemas.contract.v1.c2_behavioral import BehaviorWeeklyRecord, EngagementTrajectory
from app.schemas.contract.v1.c3_risk import AcademicRecord, ModalityContributions, RiskAssessment
from app.schemas.contract.v1.c4_intervention import InterventionOutcome
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ── Consent & Query Filter Builder ────────────────────────────────────────────

async def get_eligible_consenting_pids(db: AsyncIOMotorDatabase) -> Set[str]:
    """
    Computes the set of student PIDs authorized to have their data exported:
    1. Students with latest decision 'accepted' for the currently active consent notice version.
    2. Students with an identity imported from OULAD (is_imported == True or source == 'oulad').
    If no consent notice is active, ONLY OULAD identities qualify.
    A student who withdraws consent is omitted from the active consent set and immediately ceases export.
    """
    # 1. Resolve active consent notice
    active_notice = await db[col.CONSENT_NOTICES].find_one({"is_active": True})

    # 2. OULAD imported identities from identity_vault
    oulad_cursor = db[col.IDENTITY_VAULT].find(
        {"$or": [{"is_imported": True}, {"source": "oulad"}]},
        {"_id": 0, "pid": 1},
    )
    oulad_pids: Set[str] = {d["pid"] async for d in oulad_cursor if d.get("pid")}

    if not active_notice:
        return oulad_pids

    active_version = active_notice["version"]
    pipeline = [
        {"$match": {"notice_version": active_version}},
        {"$sort": {"timestamp": -1}},
        {
            "$group": {
                "_id": "$pid",
                "latest_decision": {"$first": "$decision"},
            }
        },
        {"$match": {"latest_decision": "accepted"}},
    ]
    cursor = db[col.CONSENT_RECORDS].aggregate(pipeline)
    consenting_pids: Set[str] = {doc["_id"] async for doc in cursor if doc.get("_id")}

    return consenting_pids.union(oulad_pids)


def parse_ingested_since(val: Optional[Union[str, datetime]]) -> Optional[datetime]:
    """
    Safely parses an ingested_since query parameter (str or datetime) into a UTC-aware datetime.
    Replaces spaces with '+' to handle URL-decoded timezone offsets gracefully.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    val_str = str(val).strip()
    if not val_str:
        return None
    try:
        # Handles raw queries where '+' was decoded into ' ' in query strings
        val_clean = val_str.replace(" ", "+")
        dt = datetime.fromisoformat(val_clean)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ingested_since format '{val}'. Expected ISO 8601 datetime.",
        )


async def build_export_filter(
    db: AsyncIOMotorDatabase,
    pid_param: Optional[str] = None,
    course_id: Optional[str] = None,
    week_from: Optional[int] = None,
    week_to: Optional[int] = None,
    ingested_since: Optional[Union[datetime, str]] = None,
    risk_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs the MongoDB query filter including consent constraints.
    Computes consenting and OULAD PIDs once per request using a single aggregation.
    """
    if pid_param and not is_valid_pid(pid_param):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PID '{pid_param}'. Must adhere to Feature 5 format: STU_ followed by 8 hex characters.",
        )

    if week_from is not None and week_to is not None and week_from > week_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"week_from ({week_from}) cannot be greater than week_to ({week_to}).",
        )

    if risk_tier is not None:
        valid_tiers = {"low", "medium", "high", "critical"}
        if risk_tier.lower().strip() not in valid_tiers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid risk_tier '{risk_tier}'. Must be one of: {sorted(list(valid_tiers))}.",
            )

    and_clauses: List[Dict[str, Any]] = []

    # 1. Resolve eligible PIDs
    eligible_pids = await get_eligible_consenting_pids(db)

    if pid_param:
        if pid_param in eligible_pids:
            and_clauses.append({"pid": pid_param})
        else:
            # Student did not accept current notice: allow only if record is tagged oulad
            and_clauses.append({"pid": pid_param, "source": "oulad"})
    else:
        if eligible_pids:
            and_clauses.append({"$or": [{"source": "oulad"}, {"pid": {"$in": list(eligible_pids)}}]})
        else:
            and_clauses.append({"source": "oulad"})

    # 2. Add course & week range filters
    if course_id:
        and_clauses.append({"course_id": course_id.strip()})

    if week_from is not None or week_to is not None:
        week_filter: Dict[str, Any] = {}
        if week_from is not None:
            week_filter["$gte"] = week_from
        if week_to is not None:
            week_filter["$lte"] = week_to
        and_clauses.append({"week_index": week_filter})

    parsed_since = parse_ingested_since(ingested_since)
    if parsed_since is not None:
        and_clauses.append({"ingested_at": {"$gte": parsed_since}})

    if risk_tier is not None:
        and_clauses.append({"risk_tier": risk_tier.lower().strip()})

    if len(and_clauses) == 1:
        return and_clauses[0]
    elif len(and_clauses) > 1:
        return {"$and": and_clauses}
    return {}


def _get_request_id(request: Request) -> str:
    """Extracts or generates correlation request ID."""
    return (
        getattr(request.state, "request_id", None)
        or request.headers.get("x-request-id")
        or str(uuid.uuid4())
    )


# ── GET /api/v1/export/messages ───────────────────────────────────────────────

@router.get(
    "/messages",
    response_model=Envelope[List[TextMessageRecord]],
    summary="Export scrubbed discussion messages (Component 1)",
    description="Serves de-identified text messages for affective state detection.",
)
async def export_messages(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("c1")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[TextMessageRecord]]:
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
    )

    total_count = await db[col.MESSAGES].count_documents(filter_q)
    skip = (page - 1) * page_size

    # Stable sort: (course_id, week_index, pid, timestamp)
    cursor = (
        db[col.MESSAGES]
        .find(filter_q)
        .sort([("course_id", 1), ("week_index", 1), ("pid", 1), ("timestamp", 1)])
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    records: List[TextMessageRecord] = []
    skipped_count = 0

    for d in docs:
        clean_text = d.get("clean_text", "")
        # Safety net: Drop and count any record that inadvertently contains email or reg ID pattern
        if EMAIL_REGEX.search(clean_text) or REG_ID_REGEX.search(clean_text):
            skipped_count += 1
            continue

        raw_ts = d.get("timestamp") or datetime.now(timezone.utc)
        if raw_ts.tzinfo is None:
            ts = raw_ts.replace(tzinfo=timezone.utc)
        else:
            ts = raw_ts.astimezone(timezone.utc)

        records.append(
            TextMessageRecord(
                message_id=str(d["message_id"]),
                pid=str(d["pid"]),
                course_id=str(d["course_id"]),
                week_index=int(d["week_index"]),
                source_type=d["source_type"],
                clean_text=clean_text,
                timestamp=ts,
                response_latency_seconds=d.get("response_latency_seconds"),
                message_length_chars=int(d.get("message_length_chars", len(clean_text))),
                message_length_words=int(d.get("message_length_words", len(clean_text.split()))),
                reply_to_id=str(d["reply_to_id"]) if d.get("reply_to_id") else None,
            )
        )

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="messages",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[TextMessageRecord]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/behavior ───────────────────────────────────────────────

@router.get(
    "/behavior",
    response_model=Envelope[List[BehaviorWeeklyRecord]],
    summary="Export weekly behavioral engagement telemetry (Component 2)",
    description="Serves weekly engagement clickstream and video telemetry for trajectory classification.",
)
async def export_behavior(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("c2")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[BehaviorWeeklyRecord]]:
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
    )

    total_count = await db[col.BEHAVIOR_WEEKLY].count_documents(filter_q)
    skip = (page - 1) * page_size

    # Stable sort: (course_id, week_index, pid)
    cursor = (
        db[col.BEHAVIOR_WEEKLY]
        .find(filter_q)
        .sort([("course_id", 1), ("week_index", 1), ("pid", 1)])
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    records: List[BehaviorWeeklyRecord] = []
    skipped_count = 0
    for d in docs:
        try:
            records.append(
                BehaviorWeeklyRecord(
                    pid=str(d["pid"]),
                    course_id=str(d["course_id"]),
                    week_index=int(d["week_index"]),
                    login_count=max(0, int(d.get("login_count", 0))),
                    session_minutes=max(0.0, float(d.get("session_minutes", 0.0))),
                    clicks=max(0, int(d.get("clicks", 0))),
                    video_play_count=max(0, int(d.get("video_play_count", 0))),
                    video_pause_count=max(0, int(d.get("video_pause_count", 0))),
                    video_rewind_count=max(0, int(d.get("video_rewind_count", 0))),
                    video_skip_count=max(0, int(d.get("video_skip_count", 0))),
                    video_completion_pct=max(0.0, min(100.0, float(d.get("video_completion_pct", 0.0)))),
                    submissions_count=max(0, int(d.get("submissions_count", 0))),
                    avg_submission_delay_hours=float(d.get("avg_submission_delay_hours", 0.0)),
                )
            )
        except Exception:
            skipped_count += 1

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="behavior",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[BehaviorWeeklyRecord]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/academic ───────────────────────────────────────────────

@router.get(
    "/academic",
    response_model=Envelope[List[AcademicRecord]],
    summary="Export derived academic records (Component 3)",
    description="Serves derived continuous assessment, midterm, quiz, and attendance records.",
)
async def export_academic(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("c3")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[AcademicRecord]]:
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
    )

    # Aggregate distinct student-course-weeks across grades and attendance
    agg_pipeline = [
        {"$match": filter_q},
        {"$project": {"course_id": 1, "week_index": 1, "pid": 1}},
        {
            "$unionWith": {
                "coll": col.ATTENDANCE,
                "pipeline": [
                    {"$match": filter_q},
                    {"$project": {"course_id": 1, "week_index": 1, "pid": 1}},
                ],
            }
        },
        {
            "$group": {
                "_id": {
                    "course_id": "$course_id",
                    "week_index": "$week_index",
                    "pid": "$pid",
                }
            }
        },
        {
            "$sort": {
                "_id.course_id": 1,
                "_id.week_index": 1,
                "_id.pid": 1,
            }
        },
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "items": [
                    {"$skip": (page - 1) * page_size},
                    {"$limit": page_size},
                ],
            }
        },
    ]

    agg_res = await db[col.GRADES].aggregate(agg_pipeline).to_list(length=1)
    facet = agg_res[0] if agg_res else {"total": [], "items": []}
    total_count = facet["total"][0]["count"] if facet["total"] else 0
    page_keys = [item["_id"] for item in facet["items"]]

    records: List[AcademicRecord] = []

    if page_keys:
        page_pids = list({k["pid"] for k in page_keys})
        page_courses = list({k["course_id"] for k in page_keys})
        page_weeks = list({k["week_index"] for k in page_keys})

        # Fetch underlying items in batch
        grades_cursor = db[col.GRADES].find({
            "pid": {"$in": page_pids},
            "course_id": {"$in": page_courses},
            "week_index": {"$in": page_weeks},
        })
        grades_docs = await grades_cursor.to_list(length=5000)

        att_cursor = db[col.ATTENDANCE].find({
            "pid": {"$in": page_pids},
            "course_id": {"$in": page_courses},
            "week_index": {"$in": page_weeks},
        })
        att_docs = await att_cursor.to_list(length=5000)

        asg_cursor = db[col.ASSIGNMENTS].find({"course_id": {"$in": page_courses}})
        asg_docs = await asg_cursor.to_list(length=5000)
        asg_map = {str(a.get("assignment_id")): a for a in asg_docs}

        # Index assignments by week for matching submissions
        asg_ids_by_course_week: Dict[tuple, List[str]] = {}
        for a in asg_docs:
            c_key = (str(a.get("course_id")), int(a.get("week_index", 0)))
            asg_ids_by_course_week.setdefault(c_key, []).append(str(a.get("assignment_id")))

        sub_cursor = db[col.SUBMISSIONS].find({
            "pid": {"$in": page_pids},
            "course_id": {"$in": page_courses},
        })
        sub_docs = await sub_cursor.to_list(length=5000)

        quizzes_cursor = db[col.QUIZZES].find({"course_id": {"$in": page_courses}})
        quizzes_docs = await quizzes_cursor.to_list(length=5000)
        quizzes_map = {str(q.get("quiz_id")): q for q in quizzes_docs}

        # Index quiz IDs by course week
        quiz_ids_by_course_week: Dict[tuple, List[str]] = {}
        for q in quizzes_docs:
            c_key = (str(q.get("course_id")), int(q.get("week_index", 0)))
            quiz_ids_by_course_week.setdefault(c_key, []).append(str(q.get("quiz_id")))

        qa_cursor = db[col.QUIZ_ATTEMPTS].find({
            "pid": {"$in": page_pids},
            "course_id": {"$in": page_courses},
        })
        qa_docs = await qa_cursor.to_list(length=5000)

        # Index grouped items by (pid, course_id, week_index)
        grades_by_key: Dict[tuple, List[Dict[str, Any]]] = {}
        for g in grades_docs:
            k = (str(g.get("pid")), str(g.get("course_id")), int(g.get("week_index", 0)))
            grades_by_key.setdefault(k, []).append(g)

        att_by_key: Dict[tuple, Dict[str, Any]] = {}
        for a in att_docs:
            k = (str(a.get("pid")), str(a.get("course_id")), int(a.get("week_index", 0)))
            att_by_key[k] = a

        # Index submissions by (pid, course_id, assignment_id)
        subs_by_pid_course_asg: Dict[tuple, List[Dict[str, Any]]] = {}
        for s in sub_docs:
            k = (str(s.get("pid")), str(s.get("course_id")), str(s.get("assignment_id")))
            subs_by_pid_course_asg.setdefault(k, []).append(s)

        # Index quiz attempts by (pid, course_id, quiz_id)
        qa_by_pid_course_quiz: Dict[tuple, List[Dict[str, Any]]] = {}
        for qa in qa_docs:
            k = (str(qa.get("pid")), str(qa.get("course_id")), str(qa.get("quiz_id")))
            qa_by_pid_course_quiz.setdefault(k, []).append(qa)

        # Assemble AcademicRecord for each key on the page
        skipped_count = 0
        for item in page_keys:
            c_id = str(item["course_id"])
            w_idx = int(item["week_index"])
            s_pid = str(item["pid"])
            k = (s_pid, c_id, w_idx)

            k_grades = grades_by_key.get(k, [])
            k_att = att_by_key.get(k)

            # Submissions for this week's assignments
            target_asg_ids = asg_ids_by_course_week.get((c_id, w_idx), [])
            k_subs: List[Dict[str, Any]] = []
            for aid in target_asg_ids:
                k_subs.extend(subs_by_pid_course_asg.get((s_pid, c_id, aid), []))

            # Quiz attempts for this week's quizzes
            target_quiz_ids = quiz_ids_by_course_week.get((c_id, w_idx), [])
            k_qa: List[Dict[str, Any]] = []
            for qid in target_quiz_ids:
                k_qa.extend(qa_by_pid_course_quiz.get((s_pid, c_id, qid), []))

            try:
                rec = build_academic_record(
                    pid=s_pid,
                    course_id=c_id,
                    week_index=w_idx,
                    grades=k_grades,
                    attendance=k_att,
                    submissions=k_subs,
                    quiz_attempts=k_qa,
                    quizzes_map=quizzes_map,
                    assignments_map=asg_map,
                )
                records.append(rec)
            except Exception:
                skipped_count += 1
    else:
        skipped_count = 0

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="academic",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[AcademicRecord]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/affective ──────────────────────────────────────────────

@router.get(
    "/affective",
    response_model=Envelope[List[AffectiveWeeklyVector]],
    summary="Export weekly affective distress vectors (Component 3 & Component 4)",
    description="Serves aggregated weekly emotion probability distributions and dominant stress markers.",
)
async def export_affective(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    ingested_since: Optional[str] = Query(None, description="Filter records ingested at or after this UTC timestamp"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("affective")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[AffectiveWeeklyVector]]:
    parsed_since = parse_ingested_since(ingested_since)
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
        ingested_since=parsed_since,
    )

    total_count = await db[col.AFFECTIVE_WEEKLY].count_documents(filter_q)
    skip = (page - 1) * page_size

    # Stable sort: (course_id, week_index, pid)
    cursor = (
        db[col.AFFECTIVE_WEEKLY]
        .find(
            filter_q,
            {
                "_id": 0,
                "pid": 1,
                "course_id": 1,
                "week_index": 1,
                "emotion_scores": 1,
                "stress_label": 1,
                "confidence": 1,
                "message_count": 1,
                "top_drivers": 1,
            },
        )
        .sort([("course_id", 1), ("week_index", 1), ("pid", 1)])
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    records: List[AffectiveWeeklyVector] = []
    skipped_count = 0

    for d in docs:
        try:
            stress_label = str(d.get("stress_label", ""))
            if EMAIL_REGEX.search(stress_label) or REG_ID_REGEX.search(stress_label):
                skipped_count += 1
                continue

            top_drivers: List[TopDriver] = []
            has_pii = False
            for td in d.get("top_drivers", []):
                tok = str(td.get("token_or_marker", ""))
                if EMAIL_REGEX.search(tok) or REG_ID_REGEX.search(tok):
                    has_pii = True
                    break
                top_drivers.append(TopDriver(token_or_marker=tok, weight=float(td.get("weight", 0.0))))
            if has_pii:
                skipped_count += 1
                continue

            emotion_scores = {
                (DistressClass(k) if isinstance(k, str) else k): float(v)
                for k, v in d.get("emotion_scores", {}).items()
            }

            records.append(
                AffectiveWeeklyVector(
                    pid=str(d["pid"]),
                    course_id=str(d["course_id"]),
                    week_index=int(d["week_index"]),
                    emotion_scores=emotion_scores,
                    stress_label=stress_label,
                    confidence=float(d["confidence"]),
                    message_count=int(d["message_count"]),
                    top_drivers=top_drivers,
                )
            )
        except Exception:
            skipped_count += 1

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="affective",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
                "ingested_since": parsed_since.isoformat() if parsed_since else None,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[AffectiveWeeklyVector]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/trajectory ─────────────────────────────────────────────

@router.get(
    "/trajectory",
    response_model=Envelope[List[EngagementTrajectory]],
    summary="Export weekly engagement trajectories (Component 3 & Component 4)",
    description="Serves weekly behavioral engagement trend classifications (stable, improving, declining, volatile).",
)
async def export_trajectory(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    ingested_since: Optional[str] = Query(None, description="Filter records ingested at or after this UTC timestamp"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("trajectory")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[EngagementTrajectory]]:
    parsed_since = parse_ingested_since(ingested_since)
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
        ingested_since=parsed_since,
    )

    total_count = await db[col.ENGAGEMENT_TRAJECTORIES].count_documents(filter_q)
    skip = (page - 1) * page_size

    # Stable sort: (course_id, week_index, pid)
    cursor = (
        db[col.ENGAGEMENT_TRAJECTORIES]
        .find(
            filter_q,
            {
                "_id": 0,
                "pid": 1,
                "course_id": 1,
                "week_index": 1,
                "trajectory_label": 1,
                "confidence": 1,
                "contributing_indicators": 1,
            },
        )
        .sort([("course_id", 1), ("week_index", 1), ("pid", 1)])
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    records: List[EngagementTrajectory] = []
    skipped_count = 0

    for d in docs:
        try:
            indicators: List[str] = []
            has_pii = False
            for ind in d.get("contributing_indicators", []):
                s_ind = str(ind)
                if EMAIL_REGEX.search(s_ind) or REG_ID_REGEX.search(s_ind):
                    has_pii = True
                    break
                indicators.append(s_ind)
            if has_pii:
                skipped_count += 1
                continue

            records.append(
                EngagementTrajectory(
                    pid=str(d["pid"]),
                    course_id=str(d["course_id"]),
                    week_index=int(d["week_index"]),
                    trajectory_label=TrajectoryLabel(d["trajectory_label"]),
                    confidence=float(d["confidence"]),
                    contributing_indicators=indicators,
                )
            )
        except Exception:
            skipped_count += 1

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="trajectory",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
                "ingested_since": parsed_since.isoformat() if parsed_since else None,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[EngagementTrajectory]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/risk ───────────────────────────────────────────────────

@router.get(
    "/risk",
    response_model=Envelope[List[RiskAssessment]],
    summary="Export multimodal student risk assessments (Component 4)",
    description="Serves unified disengagement risk scores, tiers, and modality breakdowns.",
)
async def export_risk(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_from: Optional[int] = Query(None, ge=0, description="Start week index"),
    week_to: Optional[int] = Query(None, ge=0, description="End week index"),
    pid: Optional[str] = Query(None, description="Pseudonymized student ID (STU_xxxxxxxx)"),
    risk_tier: Optional[str] = Query(None, description="Categorical risk tier (low, medium, high, critical)"),
    ingested_since: Optional[str] = Query(None, description="Filter records ingested at or after this UTC timestamp"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("risk")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[RiskAssessment]]:
    parsed_since = parse_ingested_since(ingested_since)
    filter_q = await build_export_filter(
        db=db,
        pid_param=pid,
        course_id=course_id,
        week_from=week_from,
        week_to=week_to,
        ingested_since=parsed_since,
        risk_tier=risk_tier,
    )

    total_count = await db[col.RISK_ASSESSMENTS].count_documents(filter_q)
    skip = (page - 1) * page_size

    # Stable sort: (course_id, week_index, pid)
    cursor = (
        db[col.RISK_ASSESSMENTS]
        .find(
            filter_q,
            {
                "_id": 0,
                "pid": 1,
                "course_id": 1,
                "week_index": 1,
                "risk_score": 1,
                "risk_tier": 1,
                "modality_contributions": 1,
                "top_drivers": 1,
            },
        )
        .sort([("course_id", 1), ("week_index", 1), ("pid", 1)])
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    records: List[RiskAssessment] = []
    skipped_count = 0

    for d in docs:
        try:
            top_drivers: List[str] = []
            has_pii = False
            for drv in d.get("top_drivers", []):
                s_drv = str(drv)
                if EMAIL_REGEX.search(s_drv) or REG_ID_REGEX.search(s_drv):
                    has_pii = True
                    break
                top_drivers.append(s_drv)
            if has_pii:
                skipped_count += 1
                continue

            mc = d["modality_contributions"]
            records.append(
                RiskAssessment(
                    pid=str(d["pid"]),
                    course_id=str(d["course_id"]),
                    week_index=int(d["week_index"]),
                    risk_score=float(d["risk_score"]),
                    risk_tier=RiskTier(d["risk_tier"]),
                    modality_contributions=ModalityContributions(
                        affective=float(mc["affective"]),
                        behavioral=float(mc["behavioral"]),
                        academic=float(mc["academic"]),
                    ),
                    top_drivers=top_drivers,
                )
            )
        except Exception:
            skipped_count += 1

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="risk",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "course_id": course_id,
                "week_from": week_from,
                "week_to": week_to,
                "pid": pid,
                "risk_tier": risk_tier,
                "ingested_since": parsed_since.isoformat() if parsed_since else None,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[RiskAssessment]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )


# ── GET /api/v1/export/outcomes ───────────────────────────────────────────────

@router.get(
    "/outcomes",
    response_model=Envelope[List[InterventionOutcome]],
    summary="Export intervention outcomes feedback loop (Component 4)",
    description="Serves recorded staff intervention decisions and observed changes for recommendation refinement.",
)
async def export_outcomes(
    request: Request,
    recommendation_id: Optional[str] = Query(None, description="Specific recommendation identifier"),
    ingested_since: Optional[str] = Query(None, description="Filter records ingested at or after this UTC timestamp"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
    actor: ExportActor = Depends(export_actor("outcomes")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Envelope[List[InterventionOutcome]]:
    # 1. Resolve consenting and OULAD PIDs
    eligible_pids = await get_eligible_consenting_pids(db)

    # 2. Filter recommendations belonging to eligible students
    rec_query: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}
    if recommendation_id:
        rec_query["recommendation_id"] = recommendation_id
    eligible_rec_ids = set(await db[col.RECOMMENDATIONS].distinct("recommendation_id", rec_query))

    # 3. Build outcome query filters
    parsed_since = parse_ingested_since(ingested_since)
    base_filter: Dict[str, Any] = {}
    if recommendation_id:
        base_filter["recommendation_id"] = recommendation_id
    if parsed_since is not None:
        base_filter["ingested_at"] = {"$gte": parsed_since}

    total_base = await db[col.INTERVENTION_OUTCOMES].count_documents(base_filter)

    final_filter = dict(base_filter)
    final_filter["recommendation_id"] = {"$in": list(eligible_rec_ids)}
    total_count = await db[col.INTERVENTION_OUTCOMES].count_documents(final_filter) if eligible_rec_ids else 0

    ineligible_or_missing_rec_count = total_base - total_count
    skipped_count = max(0, ineligible_or_missing_rec_count)

    skip = (page - 1) * page_size
    docs: List[Dict[str, Any]] = []
    if eligible_rec_ids:
        cursor = (
            db[col.INTERVENTION_OUTCOMES]
            .find(
                final_filter,
                {
                    "_id": 0,
                    "recommendation_id": 1,
                    "decision": 1,
                    "completed": 1,
                    "observed_change": 1,
                    "notes_present": 1,
                },
            )
            .sort([("recommendation_id", 1)])
            .skip(skip)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)

    records: List[InterventionOutcome] = []
    for d in docs:
        try:
            obs = d.get("observed_change")
            obs_str = str(obs) if obs is not None else None
            if obs_str and (EMAIL_REGEX.search(obs_str) or REG_ID_REGEX.search(obs_str)):
                skipped_count += 1
                continue

            records.append(
                InterventionOutcome(
                    recommendation_id=str(d["recommendation_id"]),
                    decision=Decision(d["decision"]),
                    completed=bool(d["completed"]),
                    observed_change=obs_str,
                    notes_present=bool(d["notes_present"]),
                )
            )
        except Exception:
            skipped_count += 1

    # Critical audit log write: MUST succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        target_type="export",
        target_id="outcomes",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "filters": {
                "recommendation_id": recommendation_id,
                "ingested_since": ingested_since.isoformat() if ingested_since else None,
            },
            "row_count": len(records),
            "skipped_count": skipped_count,
            "page": page,
        },
    )

    return Envelope[List[InterventionOutcome]](
        schema_version=CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc),
        source=ComponentSource.LMS,
        request_id=_get_request_id(request),
        data=records,
        page=page,
        page_size=page_size,
        total=total_count,
    )
