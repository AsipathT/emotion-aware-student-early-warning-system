"""
backend/app/routers/staff_outcomes.py

Feature 35: Staff Intervention Outcome Recording Router (Component 4 FR8/FR9).
Provides objective comparative suggestions, outcome finalization, and canonical
feedback loop synchronization with strictly redacted observed change summaries.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.privacy import scrub_text
from app.db import collections as col
from app.db.storage_models import Decision, InterventionOutcomeStorage
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.staff_outcomes import (
    OutcomeDeltaItem,
    OutcomeRecordRequest,
    OutcomeRecordResponse,
    OutcomeSuggestionResponse,
)
from app.services.audit import log_event
from app.services.intervention_events import on_intervention_completed
from app.services.intervention_service import change_status
from app.services.outcome_metrics import (
    build_observed_change_text,
    compute_outcome_delta,
    weeks_to_improvement,
)
from app.services.staff_access import require_staff, validate_pid
from app.services.student_context import get_analytics_snapshot

logger = logging.getLogger("app.staff_outcomes")

router = APIRouter(
    prefix="/api/v1/staff/outcomes",
    tags=["Staff Outcomes"],
)


@router.get(
    "/{intervention_id}/suggestion",
    response_model=OutcomeSuggestionResponse,
    summary="Get objective outcome delta suggestion",
)
async def get_outcome_suggestion(
    intervention_id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Computes before/after metrics comparing the baseline snapshot with the latest C1/C2/C3 outputs.
    Returns calculated risk reduction, tier transition, trajectory change, and weeks to improvement.
    """
    clean_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({
        "$or": [{"id": clean_id}, {"_id": clean_id}]
    })
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    pid = rec.get("pid")
    course_id = rec.get("course_id")
    baseline = rec.get("baseline_snapshot") or {}

    # Followup snapshot from latest analytics
    followup = await get_analytics_snapshot(db, pid, course_id)

    # Risk and trajectory history for weeks to improvement computation
    b_week = int(baseline.get("week_index") or 0)
    risk_history = await db[col.RISK_ASSESSMENTS].find(
        {"pid": pid, "course_id": course_id, "week_index": {"$gt": b_week}}
    ).sort("week_index", 1).to_list(100)
    traj_history = await db[col.ENGAGEMENT_TRAJECTORIES].find(
        {"pid": pid, "course_id": course_id, "week_index": {"$gt": b_week}}
    ).sort("week_index", 1).to_list(100)

    delta = compute_outcome_delta(baseline, followup)
    weeks = weeks_to_improvement(baseline, risk_history, traj_history)

    curr_status = str(rec.get("status", "")).strip().lower()
    is_recorded = "outcome" in rec and rec["outcome"] is not None
    can_record = (curr_status in {"accepted", "in_progress"}) and not is_recorded

    return OutcomeSuggestionResponse(
        intervention_id=clean_id,
        current_status=curr_status,
        can_record=can_record,
        baseline=baseline,
        latest=followup,
        delta=OutcomeDeltaItem(**delta),
        weeks_to_improvement=weeks,
        suggested_direction=delta["direction"],
        is_recorded=is_recorded,
        outcome=rec.get("outcome"),
    )


@router.post(
    "/{intervention_id}",
    response_model=OutcomeRecordResponse,
    summary="Record final intervention outcome",
)
async def record_intervention_outcome(
    intervention_id: str,
    payload: OutcomeRecordRequest,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Records intervention completion or discontinuation, objective evidence deltas,
    and counselor clinical notes. Enforces research integrity (outcomes are immutable).
    """
    clean_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({
        "$or": [{"id": clean_id}, {"_id": clean_id}]
    })
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    # 1. Enforce immutability
    if rec.get("outcome"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Outcome has already been recorded for this intervention. Recorded outcomes are immutable.",
        )

    # 2. Status validity check (allowed only from accepted or in_progress)
    curr_status = str(rec.get("status", "")).strip().lower()
    if curr_status not in {"accepted", "in_progress"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot record outcome for intervention in state '{curr_status}'. "
                "Outcome recording is permitted only when status is 'accepted' or 'in_progress'."
            ),
        )

    # 3. Compute objective metrics and deltas
    pid = rec.get("pid")
    course_id = rec.get("course_id")
    baseline = rec.get("baseline_snapshot") or {}
    followup = await get_analytics_snapshot(db, pid, course_id)

    b_week = int(baseline.get("week_index") or 0)
    risk_history = await db[col.RISK_ASSESSMENTS].find(
        {"pid": pid, "course_id": course_id, "week_index": {"$gt": b_week}}
    ).sort("week_index", 1).to_list(100)
    traj_history = await db[col.ENGAGEMENT_TRAJECTORIES].find(
        {"pid": pid, "course_id": course_id, "week_index": {"$gt": b_week}}
    ).sort("week_index", 1).to_list(100)

    delta = compute_outcome_delta(baseline, followup)
    weeks = weeks_to_improvement(baseline, risk_history, traj_history)

    # 4. Privacy scrubber on summary
    clean_summary: Optional[str] = None
    if payload.summary:
        clean_text_val, _ = scrub_text(payload.summary)
        clean_summary = clean_text_val[:300]

    now_utc = datetime.now(timezone.utc)
    outcome_doc = {
        "result": payload.result,
        "category": payload.staff_category,
        "delta": delta,
        "weeks_to_improvement": weeks,
        "summary": clean_summary,
        "staff_notes": payload.staff_notes,
        "recorded_by": str(current_user.id),
        "recorded_at": now_utc,
    }

    # 5. Advance lifecycle state (completed or cancelled)
    target_status = "completed" if payload.result == "completed" else "cancelled"
    updated_rec = await change_status(
        db=db,
        record=rec,
        new_status=target_status,
        actor_id=str(current_user.id),
        note=f"Outcome recorded: {payload.result} ({payload.staff_category})",
    )

    # 6. Save outcome sub-document to intervention_records
    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {"$set": {"outcome": outcome_doc}},
    )

    # 7. Upsert canonical intervention_outcomes (Component 4 feedback) if originated from a recommendation
    observed_change_text: Optional[str] = None
    if rec.get("recommendation_id"):
        rec_id = str(rec["recommendation_id"]).strip()
        existing_outcome = await db[col.INTERVENTION_OUTCOMES].find_one({"recommendation_id": rec_id})
        outcome_id = (
            str(existing_outcome["_id"])
            if existing_outcome and "_id" in existing_outcome
            else str(uuid.uuid4())
        )
        dec_val = existing_outcome.get("decision", "approved") if existing_outcome else "approved"

        # Feature 39: append student-rated helpfulness if student feedback was submitted
        fb_doc = await db["intervention_feedback"].find_one({"intervention_id": clean_id})
        rating_val = int(fb_doc["helpfulness"]) if fb_doc and fb_doc.get("helpfulness") else None

        observed_change_text = build_observed_change_text(
            delta=delta,
            category=payload.staff_category,
            weeks_to_improvement=weeks,
            helpfulness_rating=rating_val,
        )

        canonical_outcome = InterventionOutcomeStorage(
            id=outcome_id,
            recommendation_id=rec_id,
            decision=Decision(dec_val),
            completed=(payload.result == "completed"),
            observed_change=observed_change_text,
            notes_present=bool(payload.staff_notes and payload.staff_notes.strip()),
        )
        await db[col.INTERVENTION_OUTCOMES].replace_one(
            {"recommendation_id": rec_id},
            canonical_outcome.model_dump(by_alias=True),
            upsert=True,
        )

    # 8. Event hook invocation (non-blocking, exception-safe)
    try:
        await on_intervention_completed(db, updated_rec)
    except Exception as exc:
        logger.warning("on_intervention_completed hook invocation failed: %s", exc)

    # 9. Audit event logging
    actor_role_str = str(getattr(current_user.role, "value", current_user.role))
    clean_student_pid = validate_pid(str(rec.get("pid", "")).strip())
    await log_event(
        request=request,
        db=db,
        action=AuditAction.STUDENT_DATA_VIEWED,
        actor_id=str(current_user.id),
        actor_role=actor_role_str,
        target_type="student",
        target_id=clean_student_pid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "view": "intervention_outcome_recorded",
            "intervention_id": clean_id,
            "result": payload.result,
            "category": payload.staff_category,
            "has_recommendation": bool(rec.get("recommendation_id")),
            "observed_change": observed_change_text,
        },
    )

    return OutcomeRecordResponse(
        intervention_id=clean_id,
        result=payload.result,
        category=payload.staff_category,
        status=target_status,
        observed_change=observed_change_text,
        weeks_to_improvement=weeks,
        recorded_at=now_utc,
        message=f"Intervention outcome successfully recorded as '{payload.result}'.",
    )
