"""
backend/app/routers/staff_students.py

Feature 31: Staff Student Context and Risk Overview Router (Component 4 Input).
Provides:
  - GET /api/v1/staff/students: Risk-stratified cohort triage overview.
  - GET /api/v1/staff/students/{pid}/context: Multi-modal student context summary.
"""

import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.db import collections as col
from app.models.user import User
from app.routers.export import get_eligible_consenting_pids
from app.schemas.staff_students import (
    StaffStudentOverviewItem,
    StaffStudentOverviewResponse,
    StudentContextResponse,
)
from app.services.affective_explain import dominant_class
from app.services.staff_access import (
    audit_student_view,
    is_pid_visible,
    require_staff,
    validate_pid,
)
from app.services.student_context import build_student_context

router = APIRouter(prefix="/api/v1/staff/students", tags=["staff-students"])

TIER_RANKS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "unknown": 0,
}


# ── GET /api/v1/staff/students ────────────────────────────────────────────────

@router.get(
    "",
    response_model=StaffStudentOverviewResponse,
    summary="List student risk assessment overview",
    description="Returns risk-stratified overview from latest risk_assessments combining C1, C2, and C3 indicators. Sorted critical -> low, then risk_score descending.",
)
async def list_student_risk_overview(
    request: Request,
    course_id: Optional[str] = Query(None, description="Course institutional identifier"),
    tier: Optional[str] = Query(None, description="Filter by risk tier (critical, high, medium, low)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffStudentOverviewResponse:
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        await audit_student_view(
            request,
            db,
            current_user,
            pid="cohort",
            view="student_list",
            course_id=course_id,
        )
        return StaffStudentOverviewResponse(
            items=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )

    match_filter: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}
    if course_id:
        match_filter["course_id"] = str(course_id).strip()
    if tier:
        match_filter["risk_tier"] = str(tier).strip().lower()

    # Aggregate latest risk assessment per (pid, course_id)
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
    raw_risks = await db[col.RISK_ASSESSMENTS].aggregate(pipeline).to_list(length=1000)

    items: List[StaffStudentOverviewItem] = []
    for r in raw_risks:
        p = str(r["pid"])
        c = str(r["course_id"])
        w = int(r.get("week_index", 0))
        tier_val = str(r.get("risk_tier") or "unknown").lower()
        score_val = round(float(r["risk_score"]), 4) if "risk_score" in r and r["risk_score"] is not None else None

        # Look up corresponding trajectory label from C2
        traj_doc = await db[col.ENGAGEMENT_TRAJECTORIES].find_one(
            {"pid": p, "course_id": c, "week_index": w}
        )
        if not traj_doc:
            # Fallback to latest trajectory doc
            traj_doc = await db[col.ENGAGEMENT_TRAJECTORIES].find_one(
                {"pid": p, "course_id": c}, sort=[("week_index", -1)]
            )
        traj_label = str(traj_doc.get("trajectory_label") or "unknown") if traj_doc else "unknown"

        # Look up dominant distress class from C1
        aff_doc = await db[col.AFFECTIVE_WEEKLY].find_one(
            {"pid": p, "course_id": c, "week_index": w}
        )
        if not aff_doc:
            aff_doc = await db[col.AFFECTIVE_WEEKLY].find_one(
                {"pid": p, "course_id": c}, sort=[("week_index", -1)]
            )
        dom_cls = "none"
        if aff_doc and aff_doc.get("emotion_scores"):
            dom_cls, _ = dominant_class(aff_doc["emotion_scores"])

        items.append(
            StaffStudentOverviewItem(
                pid=p,
                course_id=c,
                week_index=w,
                risk_score=score_val,
                risk_tier=tier_val,
                trajectory_label=traj_label,
                dominant_distress_class=dom_cls,
            )
        )

    # Sort critical -> low, then risk_score descending
    items.sort(
        key=lambda x: (
            TIER_RANKS.get(x.risk_tier, 0),
            x.risk_score if x.risk_score is not None else -1.0,
        ),
        reverse=True,
    )

    total_count = len(items)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
    start_idx = (page - 1) * page_size
    paged_items = items[start_idx : start_idx + page_size]

    # Critical audit log write
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="student_list",
        course_id=course_id,
    )

    return StaffStudentOverviewResponse(
        items=paged_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── GET /api/v1/staff/students/{pid}/context ──────────────────────────────────

@router.get(
    "/{pid}/context",
    response_model=StudentContextResponse,
    summary="Get unified multi-modal student context (C4)",
    description="Synthesizes affective distress (C1), behavioral trajectories (C2), dropout risk & modality contributions (C3), and past interventions.",
)
async def get_student_context(
    pid: str,
    request: Request,
    course_id: str = Query(..., description="Course institutional identifier (required)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StudentContextResponse:
    clean_pid = validate_pid(pid)
    cid = str(course_id).strip()
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="course_id query parameter is required.",
        )

    # Verify active research consent
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    context_data = await build_student_context(db, clean_pid, cid)

    # Verify that at least one component has recorded data for this student/course
    has_c1 = context_data["c1"]["latest"] is not None
    has_c2 = context_data["c2"]["latest"] is not None
    has_c3 = context_data["c3"]["latest"] is not None
    has_beh = len(context_data["behaviour"]["history"]) > 0

    if not (has_c1 or has_c2 or has_c3 or has_beh):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No academic or behavioral analytics records found for student '{clean_pid}' in course '{cid}'.",
        )

    # Critical audit log write: fails closed before data return
    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="student_context",
        course_id=cid,
    )

    return StudentContextResponse(**context_data)
