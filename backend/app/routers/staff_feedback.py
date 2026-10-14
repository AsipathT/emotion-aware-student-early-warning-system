"""
backend/app/routers/staff_feedback.py

Feature 39: Staff Intervention Feedback Router (Component 4 Feedback Loop).
Endpoints:
  - GET /api/v1/staff/feedback/interventions/{intervention_id}
    Retrieves full feedback (helpfulness, attended, barrier, comment) for detail panel.
  - GET /api/v1/staff/feedback/summary?intervention_type=
    Aggregates response rate, mean helpfulness, and barrier distributions.
  - GET /api/v1/staff/feedback/export
    ADMIN only: exports pseudonymous rows without comments, schema "feedback-export-1.0", audited.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.intervention_feedback import COL_INTERVENTION_FEEDBACK
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.staff_feedback import (
    FeedbackExportResponse,
    FeedbackExportRow,
    FeedbackSummaryResponse,
    StaffFeedbackDetailResponse,
)
from app.services.audit import log_event
from app.services.staff_access import require_staff

logger = logging.getLogger("app.staff_feedback")

router = APIRouter(
    prefix="/api/v1/staff/feedback",
    tags=["Staff Feedback"],
)


@router.get(
    "/interventions/{intervention_id}",
    response_model=StaffFeedbackDetailResponse,
    summary="Get student feedback for an intervention",
)
async def get_intervention_feedback(
    intervention_id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns student-reported helpfulness, attendance, barriers, and private comment
    for the specified intervention.
    """
    clean_id = str(intervention_id).strip()
    fb_doc = await db[COL_INTERVENTION_FEEDBACK].find_one({
        "$or": [{"intervention_id": clean_id}, {"id": clean_id}]
    })

    if not fb_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No feedback found for intervention '{clean_id}'.",
        )

    return StaffFeedbackDetailResponse(
        id=str(fb_doc.get("id") or fb_doc.get("_id")),
        intervention_id=str(fb_doc["intervention_id"]),
        pid=str(fb_doc["pid"]),
        intervention_type=str(fb_doc["intervention_type"]),
        helpfulness=int(fb_doc["helpfulness"]),
        attended=fb_doc["attended"],
        barrier=fb_doc.get("barrier"),
        comment=fb_doc.get("comment"),
        created_at=fb_doc["created_at"],
    )


@router.get(
    "/summary",
    response_model=FeedbackSummaryResponse,
    summary="Get aggregate student feedback metrics and response rate",
)
async def get_feedback_summary(
    intervention_type: Optional[str] = Query(default=None, description="Optional filter by intervention type"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Computes aggregate metrics:
      - n: Total feedback count
      - completed_interventions: Completed interventions count
      - response_rate: Feedback submissions / completed interventions
      - mean_helpfulness: Overall mean rating (1-5)
      - mean_helpfulness_by_type: Grouped average ratings by intervention type
      - barrier_counts: Categorical breakdown of reported barriers
      - attended_counts: Distribution of attendance confirmations
    """
    match_fb: Dict[str, Any] = {}
    match_rec: Dict[str, Any] = {"status": "completed"}

    if intervention_type and intervention_type.strip():
        clean_itype = intervention_type.strip()
        match_fb["intervention_type"] = clean_itype
        match_rec["intervention_type"] = clean_itype

    # 1. Total completed interventions in scope
    completed_count = await db[COL_INTERVENTION_RECORDS].count_documents(match_rec)

    # 2. Feedback items
    cursor = db[COL_INTERVENTION_FEEDBACK].find(match_fb)
    all_fb = await cursor.to_list(length=10000)

    n = len(all_fb)
    response_rate = round(n / completed_count, 4) if completed_count > 0 else 0.0

    total_score = sum(int(f.get("helpfulness", 0)) for f in all_fb)
    mean_helpfulness = round(total_score / n, 2) if n > 0 else 0.0

    # Groupings
    by_type_sums: Dict[str, List[int]] = {}
    barrier_counts: Dict[str, int] = {}
    attended_counts: Dict[str, int] = {}

    for f in all_fb:
        itype = str(f.get("intervention_type") or "unknown")
        by_type_sums.setdefault(itype, []).append(int(f.get("helpfulness", 0)))

        bar = f.get("barrier")
        if bar:
            barrier_counts[str(bar)] = barrier_counts.get(str(bar), 0) + 1

        att = str(f.get("attended") or "unknown")
        attended_counts[att] = attended_counts.get(att, 0) + 1

    mean_by_type = {
        itype: round(sum(scores) / len(scores), 2)
        for itype, scores in by_type_sums.items()
        if scores
    }

    return FeedbackSummaryResponse(
        n=n,
        completed_interventions=completed_count,
        response_rate=response_rate,
        mean_helpfulness=mean_helpfulness,
        mean_helpfulness_by_type=mean_by_type,
        barrier_counts=barrier_counts,
        attended_counts=attended_counts,
    )


@router.get(
    "/export",
    response_model=FeedbackExportResponse,
    summary="Export pseudonymous feedback data for C4 research (Admin only)",
)
async def export_feedback(
    request: Request,
    intervention_type: Optional[str] = Query(default=None, description="Optional filter by intervention type"),
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Administrative export of intervention feedback for research evaluation (Component 4).
    PRIVACY GUARANTEES:
      - Restricted to Administrator role.
      - Free-text comments and student real identities are completely omitted.
      - Contains pseudonymous PID, intervention type, helpfulness, attendance, and barrier.
      - Audited with AuditAction.EXPORT_GENERATED prior to data release.
    """
    match_fb: Dict[str, Any] = {}
    if intervention_type and intervention_type.strip():
        match_fb["intervention_type"] = intervention_type.strip()

    cursor = db[COL_INTERVENTION_FEEDBACK].find(match_fb).sort("created_at", -1)
    docs = await cursor.to_list(length=10000)

    rows = [
        FeedbackExportRow(
            pid=str(d["pid"]),
            intervention_type=str(d["intervention_type"]),
            helpfulness=int(d["helpfulness"]),
            attended=str(d["attended"]),
            barrier=d.get("barrier"),
            created_at=d["created_at"],
        )
        for d in docs
    ]

    # Critical audit log write: must succeed before data is returned
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="export",
        target_id="intervention_feedback",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "schema": "feedback-export-1.0",
            "row_count": len(rows),
        },
    )

    return FeedbackExportResponse(
        schema="feedback-export-1.0",
        exported_at=datetime.now(timezone.utc),
        total_count=len(rows),
        data=rows,
    )
