"""
backend/app/routers/staff_review.py

Feature 33: Human-in-the-Loop Recommendation Review Router (C4 FR7).
Provides:
  - POST /api/v1/staff/review/{recommendation_id}: Atomic review actions (approve, modify, reject).
  - GET /api/v1/staff/review/stats: Human review rate statistics verifying 100% human-control NFR.
  - assert_recommendation_reviewed: Exported assertion helper for F34 intervention actions.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.privacy import scrub_text
from app.db import collections as col
from app.db.storage_models import (
    Decision,
    InterventionOutcomeStorage,
    InterventionStorage,
)
from app.models.intervention_record import (
    COL_INTERVENTION_RECORDS,
    COL_RECOMMENDATION_REVIEWS,
    InterventionRecord,
    StatusHistoryEntry,
)
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.staff_review import (
    StaffReviewRequest,
    StaffReviewResponse,
    StaffReviewStatsResponse,
)
from app.services.audit import log_event
from app.services.intervention_catalog import is_known
from app.services.staff_access import is_pid_visible, require_staff, validate_pid
from app.services.student_context import get_analytics_snapshot

logger = logging.getLogger("app.staff_review")

router = APIRouter(prefix="/api/v1/staff/review", tags=["staff-review"])

DECIDED_STATUSES = {"approved", "modified", "rejected"}


async def assert_recommendation_reviewed(
    db: AsyncIOMotorDatabase,
    recommendation_id: str,
) -> Dict[str, Any]:
    """
    Exported governance helper for F34 and downstream decision services.
    Ensures that an intervention cannot be acted upon or dispatched unless
    its source recommendation underwent explicit human review.
    """
    clean_id = str(recommendation_id).strip()
    rev = await db[COL_RECOMMENDATION_REVIEWS].find_one({"recommendation_id": clean_id})
    if not rev:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recommendation '{clean_id}' has not been reviewed by authorized staff. Action prohibited.",
        )
    return rev


# ── GET /api/v1/staff/review/stats ───────────────────────────────────────────

@router.get(
    "/stats",
    response_model=StaffReviewStatsResponse,
    summary="Get human review coverage statistics",
    description="Returns aggregate counts of total, pending, approved, modified, and rejected recommendations to verify the 100% human-in-the-loop NFR.",
)
async def get_review_stats(
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffReviewStatsResponse:
    total = await db[col.RECOMMENDATIONS].count_documents({})
    approved = await db[col.RECOMMENDATIONS].count_documents({"status": "approved"})
    modified = await db[col.RECOMMENDATIONS].count_documents({"status": "modified"})
    rejected = await db[col.RECOMMENDATIONS].count_documents({"status": "rejected"})
    pending = await db[col.RECOMMENDATIONS].count_documents({"status": {"$nin": list(DECIDED_STATUSES)}})
    reviewed = approved + modified + rejected
    review_rate = round(float(reviewed / total), 4) if total > 0 else 0.0

    return StaffReviewStatsResponse(
        total=total,
        pending=pending,
        approved=approved,
        modified=modified,
        rejected=rejected,
        reviewed=reviewed,
        review_rate=review_rate,
    )


# ── POST /api/v1/staff/review/{recommendation_id} ─────────────────────────────

@router.post(
    "/{recommendation_id}",
    response_model=StaffReviewResponse,
    summary="Review and decide on an intervention recommendation",
    description="Atomically reviews an algorithmic recommendation: approve a candidate rank, modify to another catalog type, or reject. Records C4 feedback outcome and establishes baseline snapshot.",
)
async def review_recommendation(
    recommendation_id: str,
    payload: StaffReviewRequest,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffReviewResponse:
    clean_id = str(recommendation_id).strip()
    now_utc = datetime.now(timezone.utc)

    # 1. Fetch existing recommendation document
    rec_doc = await db[col.RECOMMENDATIONS].find_one(
        {"$or": [{"recommendation_id": clean_id}, {"_id": clean_id}]}
    )
    if not rec_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention recommendation '{clean_id}' not found.",
        )

    clean_pid = validate_pid(str(rec_doc["pid"]))

    # 2. Check student research consent
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    # Check if recommendation has already been finalized
    current_status = str(rec_doc.get("status", "proposed")).strip().lower()
    if current_status in DECIDED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recommendation '{clean_id}' has already been reviewed (status: {current_status}). Decisions are final.",
        )

    # 3. Validate chosen intervention based on decision
    candidates = rec_doc.get("candidates") or []
    sorted_candidates = sorted(candidates, key=lambda c: int(c.get("rank", 99)))
    top_cand = sorted_candidates[0] if sorted_candidates else {}

    chosen_type: Optional[str] = None
    if payload.decision == "approved":
        rank_match = next((c for c in candidates if int(c.get("rank", -1)) == payload.selected_rank), None)
        if not rank_match:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Selected candidate rank {payload.selected_rank} does not exist in recommendation '{clean_id}'.",
            )
        chosen_type = str(rank_match.get("intervention_type", "academic_support")).strip().lower()

    elif payload.decision == "modified":
        chosen_type = str(payload.modified_intervention_type).strip().lower()
        if not is_known(chosen_type):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Intervention type '{chosen_type}' is not recognized in the canonical catalog.",
            )

    elif payload.decision == "rejected":
        chosen_type = None

    # 4. Resolve and validate course_id
    target_course_id: str = ""
    if payload.course_id:
        req_cid = str(payload.course_id).strip()
        # Verify that student has data in this course
        has_enrolment = await db[col.ENROLMENTS].find_one({"pid": clean_pid, "course_id": req_cid})
        has_risk = await db[col.RISK_ASSESSMENTS].find_one({"pid": clean_pid, "course_id": req_cid})
        if not (has_enrolment or has_risk):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Course '{req_cid}' does not belong to student '{clean_pid}' records.",
            )
        target_course_id = req_cid
    else:
        # Default: lookup course of risk assessment matching week_index
        week_idx = int(rec_doc.get("week_index", 0))
        risk_doc = await db[col.RISK_ASSESSMENTS].find_one({"pid": clean_pid, "week_index": week_idx})
        if not risk_doc:
            risk_doc = await db[col.RISK_ASSESSMENTS].find_one({"pid": clean_pid}, sort=[("week_index", -1)])
        if risk_doc and risk_doc.get("course_id"):
            target_course_id = str(risk_doc["course_id"])
        else:
            enr_doc = await db[col.ENROLMENTS].find_one({"pid": clean_pid, "status": "active"})
            target_course_id = str(enr_doc["course_id"]) if enr_doc and enr_doc.get("course_id") else "GENERAL"

    # Scrub reason before atomic claim and before any DB write
    clean_reason: Optional[str] = None
    if payload.reason and payload.reason.strip():
        clean_reason, _ = scrub_text(payload.reason.strip())

    # ── Step (a): Atomic claim update ─────────────────────────────────────────
    claim_result = await db[col.RECOMMENDATIONS].update_one(
        {
            "$or": [{"recommendation_id": clean_id}, {"_id": clean_id}],
            "status": {"$nin": list(DECIDED_STATUSES)},
        },
        {
            "$set": {
                "status": payload.decision,
            }
        },
    )

    if claim_result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recommendation '{clean_id}' has already been reviewed by another staff session.",
        )

    # ── Steps (b) - (d): Protected operational writes ─────────────────────────
    interv_id: Optional[str] = None
    try:
        # (b) Insert private staff recommendation review record
        review_id = f"rev_{uuid.uuid4().hex}"
        review_doc = {
            "_id": review_id,
            "review_id": review_id,
            "recommendation_id": clean_id,
            "reviewer_id": str(current_user.id),
            "reviewer_role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            "decision": payload.decision,
            "selected_rank": payload.selected_rank,
            "chosen_intervention_type": chosen_type,
            "original_top_ranked_type": str(top_cand.get("intervention_type", "unknown")),
            "original_top_ranked_score": float(top_cand.get("suitability_score", 0.0)) if top_cand.get("suitability_score") is not None else 0.0,
            "reason": clean_reason,
            "course_id": target_course_id,
            "reviewed_at": now_utc,
        }
        await db[COL_RECOMMENDATION_REVIEWS].insert_one(review_doc)

        # (c) Upsert canonical intervention_outcomes (Component 4 feedback loop)
        existing_outcome = await db[col.INTERVENTION_OUTCOMES].find_one({"recommendation_id": clean_id})
        outcome_id = str(existing_outcome["_id"]) if existing_outcome and "_id" in existing_outcome else str(uuid.uuid4())

        canonical_outcome = InterventionOutcomeStorage(
            id=outcome_id,
            recommendation_id=clean_id,
            decision=Decision(payload.decision),
            completed=False,
            observed_change=None,
            notes_present=bool(payload.reason and payload.reason.strip()),
        )
        await db[col.INTERVENTION_OUTCOMES].replace_one(
            {"recommendation_id": clean_id},
            canonical_outcome.model_dump(by_alias=True),
            upsert=True,
        )

        # (d) If approved or modified: create canonical interventions + intervention_records
        if payload.decision in {"approved", "modified"} and chosen_type:
            interv_id = f"int_{uuid.uuid4().hex[:12]}"

            # Capture baseline analytics snapshot
            baseline_snapshot = await get_analytics_snapshot(db, clean_pid, target_course_id)

            # 1. Canonical intervention document
            canonical_interv = InterventionStorage(
                id=interv_id,
                intervention_id=interv_id,
                recommendation_id=clean_id,
                pid=clean_pid,
                course_id=target_course_id,
                intervention_type=chosen_type,
                status="approved",
                created_at=now_utc,
            )
            await db[col.INTERVENTIONS].insert_one(canonical_interv.model_dump(by_alias=True))

            # 2. Staff-side intervention record
            initial_history = StatusHistoryEntry(
                status="approved",
                at=now_utc,
                by=str(current_user.id),
                note=f"Created via recommendation review ({payload.decision}).",
            )
            operational_record = InterventionRecord(
                id=interv_id,
                recommendation_id=clean_id,
                origin="recommendation",
                pid=clean_pid,
                course_id=target_course_id,
                intervention_type=chosen_type,
                status="approved",
                created_by=str(current_user.id),
                baseline_snapshot=baseline_snapshot,
                status_history=[initial_history],
                notes=[],
                created_at=now_utc,
                updated_at=now_utc,
            )
            await db[COL_INTERVENTION_RECORDS].insert_one(operational_record.model_dump(by_alias=True))

    except Exception as exc:
        logger.critical(
            "Transaction failure following atomic claim on recommendation '%s': %s",
            clean_id,
            exc,
            exc_info=True,
        )
        # Note for manual recovery: recommendation status is claimed as '%s' but downstream
        # records may require audit reconciliation.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Recommendation '{clean_id}' was claimed but downstream record generation encountered an error: {exc}. "
                "Staff administrator intervention required."
            ),
        ) from exc

    # ── Audit logging ─────────────────────────────────────────────────────────
    actor_id = str(current_user.id)
    actor_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    try:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.RECOMMENDATION_REVIEWED,
            actor_id=actor_id,
            actor_role=actor_role,
            target_type="student",
            target_id=clean_pid,
            outcome=AuditOutcome.SUCCESS,
            details={
                "recommendation_id": clean_id,
                "decision": payload.decision,
                "chosen_intervention_type": chosen_type or "none",
                "has_reason": bool(payload.reason and payload.reason.strip()),
                "course_id": target_course_id,
                "intervention_id": interv_id or "none",
            },
        )
    except Exception as exc:
        logger.error("Audit log write failed for recommendation review (%s): %s", clean_id, exc)

    return StaffReviewResponse(
        recommendation_id=clean_id,
        decision=payload.decision,
        status=payload.decision,
        intervention_id=interv_id,
        chosen_intervention_type=chosen_type,
        reviewed_at=now_utc,
        message=f"Recommendation successfully {payload.decision}.",
    )
