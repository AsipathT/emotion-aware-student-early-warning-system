"""
backend/app/routers/staff_affective.py

Feature 30: Affective State View (SHAP / Attention) for Counsellors and Administrators.
Decision-support endpoints providing explainable root-cause insights from Component 1 (Affective State Detection).

Prefix: /api/v1/staff/affective
Tags:   ["staff-affective"]
Authorization: Counsellor or Admin role only.
"""

import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.db import collections as col
from app.models.user import User
from app.routers.export import get_eligible_consenting_pids
from app.schemas.staff_affective import (
    StaffAffectiveHistoryItem,
    StaffAffectiveHistoryResponse,
    StaffScrubbedMessageItem,
    StaffStudentListResponse,
    StaffStudentSummaryItem,
    TopDriverItem,
)
from app.services.affective_explain import (
    build_rationale,
    dominant_class,
    highlight_segments,
)
from app.services.staff_access import (
    audit_student_view,
    is_pid_visible,
    require_staff,
    validate_pid,
)

router = APIRouter(prefix="/api/v1/staff/affective", tags=["staff-affective"])


# ── GET /students ─────────────────────────────────────────────────────────────

@router.get(
    "/students",
    response_model=StaffStudentListResponse,
    summary="List student affective distress summaries",
    description="Returns latest or week-specific affective status per student for consenting cohort. Sorted by distress score descending.",
)
async def list_students(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    week_index: Optional[int] = Query(None, ge=0, description="Specific academic week (defaults to latest)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffStudentListResponse:
    # 1. Resolve eligible consenting PIDs
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        # Audit query attempt before returning empty list
        await audit_student_view(
            request,
            db,
            current_user,
            pid="cohort",
            view="students_summary",
            course_id=course_id,
            week_index=week_index,
        )
        return StaffStudentListResponse(
            items=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )

    match_filter: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}
    if course_id:
        match_filter["course_id"] = str(course_id).strip()

    if week_index is not None:
        match_filter["week_index"] = int(week_index)
        cursor = db[col.AFFECTIVE_WEEKLY].find(match_filter)
        raw_docs = await cursor.to_list(length=1000)
    else:
        # Latest week per student and course
        pipeline = [
            {"$match": match_filter},
            {"$sort": {"week_index": -1}},
            {
                "$group": {
                    "_id": {"pid": "$pid", "course_id": "$course_id"},
                    "latest_doc": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$latest_doc"}},
        ]
        raw_docs = await db[col.AFFECTIVE_WEEKLY].aggregate(pipeline).to_list(length=1000)

    # 2. Extract and format summaries
    summaries: List[StaffStudentSummaryItem] = []
    for doc in raw_docs:
        dom_cls, dom_score = dominant_class(doc.get("emotion_scores"))
        summaries.append(
            StaffStudentSummaryItem(
                pid=str(doc["pid"]),
                course_id=str(doc["course_id"]),
                week_index=int(doc["week_index"]),
                dominant_class=dom_cls,
                dominant_score=dom_score,
                stress_label=str(doc.get("stress_label") or "moderate"),
                confidence=round(float(doc.get("confidence") or 0.0), 4),
                message_count=int(doc.get("message_count") or 0),
            )
        )

    # Sort descending by dominant_score, then week_index descending
    summaries.sort(key=lambda s: (s.dominant_score, s.week_index), reverse=True)

    total_count = len(summaries)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
    start_idx = (page - 1) * page_size
    paged_items = summaries[start_idx : start_idx + page_size]

    # Critical audit log write: must succeed before data is returned
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="students_summary",
        course_id=course_id,
        week_index=week_index,
    )

    return StaffStudentListResponse(
        items=paged_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── GET /students/{pid} ───────────────────────────────────────────────────────

@router.get(
    "/students/{pid}",
    response_model=StaffAffectiveHistoryResponse,
    summary="Get longitudinal affective state history for a student",
    description="Returns chronological weekly distress vectors, dominant classes, linguistic drivers, and plain-language diagnostic rationale.",
)
async def get_student_history(
    pid: str,
    request: Request,
    course_id: str = Query(..., description="Course institutional identifier (required)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffAffectiveHistoryResponse:
    clean_pid = validate_pid(pid)
    cid = str(course_id).strip()
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="course_id parameter is required.",
        )

    # Check active consent visibility
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    # Retrieve all weekly records ascending
    cursor = (
        db[col.AFFECTIVE_WEEKLY]
        .find({"pid": clean_pid, "course_id": cid})
        .sort("week_index", 1)
    )
    docs = await cursor.to_list(length=100)
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No affective state records found for student '{clean_pid}' in course '{cid}'.",
        )

    history_items: List[StaffAffectiveHistoryItem] = []
    for idx, doc in enumerate(docs):
        prev_doc = docs[idx - 1] if idx > 0 else None
        dom_cls, dom_score = dominant_class(doc.get("emotion_scores"))
        rationale = build_rationale(doc, prev_doc)

        top_drivers_raw = doc.get("top_drivers") or []
        drivers_list: List[TopDriverItem] = []
        for d in top_drivers_raw:
            tok = d.get("token_or_marker") or d.get("token")
            if tok and str(tok).strip():
                drivers_list.append(
                    TopDriverItem(
                        token_or_marker=str(tok).strip(),
                        weight=round(float(d.get("weight", 0.0)), 4),
                    )
                )

        history_items.append(
            StaffAffectiveHistoryItem(
                week_index=int(doc["week_index"]),
                emotion_scores={
                    k: round(float(v), 4)
                    for k, v in (doc.get("emotion_scores") or {}).items()
                },
                stress_label=str(doc.get("stress_label") or "moderate"),
                confidence=round(float(doc.get("confidence") or 0.0), 4),
                message_count=int(doc.get("message_count") or 0),
                top_drivers=drivers_list,
                dominant_class=dom_cls,
                dominant_score=dom_score,
                rationale=rationale,
            )
        )

    # Critical audit log write: fails closed before returning data
    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="affective_history",
        course_id=cid,
    )

    return StaffAffectiveHistoryResponse(
        pid=clean_pid,
        course_id=cid,
        history=history_items,
    )


# ── GET /students/{pid}/messages ──────────────────────────────────────────────

@router.get(
    "/students/{pid}/messages",
    response_model=List[StaffScrubbedMessageItem],
    summary="Get scrubbed student messages with linguistic attention highlights",
    description="Returns de-identified messages from canonical 'messages' collection with attention token highlights. Raw texts are never served.",
)
async def get_student_messages(
    pid: str,
    request: Request,
    course_id: str = Query(..., description="Course institutional identifier (required)"),
    week_index: int = Query(..., ge=0, description="Academic week index (required)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[StaffScrubbedMessageItem]:
    clean_pid = validate_pid(pid)
    cid = str(course_id).strip()
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="course_id parameter is required.",
        )

    # Check active consent visibility
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    # Fetch top drivers for this student, course, and week to drive token highlighting
    affective_doc = await db[col.AFFECTIVE_WEEKLY].find_one({
        "pid": clean_pid,
        "course_id": cid,
        "week_index": int(week_index),
    })
    top_drivers = affective_doc.get("top_drivers") or [] if affective_doc else []

    # Query canonical messages collection ONLY (strictly scrubbed text)
    cursor = (
        db[col.MESSAGES]
        .find({
            "pid": clean_pid,
            "course_id": cid,
            "week_index": int(week_index),
        })
        .sort("timestamp", 1)
        .limit(50)
    )
    raw_messages = await cursor.to_list(length=50)

    # Critical audit log write: separate audit record with view="scrubbed_messages"
    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="scrubbed_messages",
        course_id=cid,
        week_index=week_index,
    )

    result_items: List[StaffScrubbedMessageItem] = []
    for msg in raw_messages:
        clean_text = str(msg.get("clean_text") or "")
        segments = highlight_segments(clean_text, top_drivers)
        result_items.append(
            StaffScrubbedMessageItem(
                message_id=str(msg.get("message_id") or msg.get("_id")),
                source_type=str(msg.get("source_type") or "unknown"),
                timestamp=msg["timestamp"],
                segments=segments,
            )
        )

    return result_items
