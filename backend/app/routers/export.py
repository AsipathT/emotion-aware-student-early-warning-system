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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.academic_derivation import build_academic_record
from app.core.component_auth import ExportActor, export_actor
from app.core.contract_version import CONTRACT_VERSION
from app.core.database import get_db
from app.core.privacy import EMAIL_REGEX, REG_ID_REGEX, is_valid_pid
from app.db import collections as col
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import ComponentSource, Envelope
from app.schemas.contract.v1.c1_affective import TextMessageRecord
from app.schemas.contract.v1.c2_behavioral import BehaviorWeeklyRecord
from app.schemas.contract.v1.c3_risk import AcademicRecord
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ── Consent & Query Filter Builder ────────────────────────────────────────────

async def build_export_filter(
    db: AsyncIOMotorDatabase,
    pid_param: Optional[str] = None,
    course_id: Optional[str] = None,
    week_from: Optional[int] = None,
    week_to: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs the MongoDB query filter including consent constraints.
    Computes consenting PIDs once per request using a single aggregation over consent_records.
    Scale notice: Using '$in: consenting_pids' is optimal for standard institutional cohorts.
    At massive scale (>100k students), an indexed consent projection flag should be utilized.
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

    # 1. Resolve active consent notice
    active_notice = await db[col.CONSENT_NOTICES].find_one({"is_active": True})

    and_clauses: List[Dict[str, Any]] = []

    if not active_notice:
        # No active notice exists: only OULAD records are eligible for export
        if pid_param:
            and_clauses.append({"pid": pid_param})
        and_clauses.append({"source": "oulad"})
    else:
        active_version = active_notice["version"]
        match_stage: Dict[str, Any] = {"notice_version": active_version}
        if pid_param:
            match_stage["pid"] = pid_param

        # Single aggregation: latest record per pid for the active notice version with decision == 'accepted'
        pipeline = [
            {"$match": match_stage},
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
        consenting_pids = [doc["_id"] async for doc in cursor]

        if pid_param:
            if pid_param in consenting_pids:
                and_clauses.append({"pid": pid_param})
            else:
                # Student did not accept current notice: only oulad records eligible
                and_clauses.append({"pid": pid_param, "source": "oulad"})
        else:
            if consenting_pids:
                and_clauses.append({"$or": [{"source": "oulad"}, {"pid": {"$in": consenting_pids}}]})
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
    for d in docs:
        records.append(
            BehaviorWeeklyRecord(
                pid=str(d["pid"]),
                course_id=str(d["course_id"]),
                week_index=int(d["week_index"]),
                login_count=int(d["login_count"]),
                session_minutes=float(d["session_minutes"]),
                clicks=int(d["clicks"]),
                video_play_count=int(d["video_play_count"]),
                video_pause_count=int(d["video_pause_count"]),
                video_rewind_count=int(d["video_rewind_count"]),
                video_skip_count=int(d["video_skip_count"]),
                video_completion_pct=float(d["video_completion_pct"]),
                submissions_count=int(d["submissions_count"]),
                avg_submission_delay_hours=float(d["avg_submission_delay_hours"]),
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
            "skipped_count": 0,
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
            "skipped_count": 0,
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
