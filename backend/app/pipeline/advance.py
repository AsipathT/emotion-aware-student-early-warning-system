"""
backend/app/pipeline/advance.py

State machine and progression engine for Feature 22: Weekly scheduler / pipeline orchestrator.
Manages stage dependencies (lms_aggregation -> c1 & c2 -> c3 -> c4), evaluates coverage against
PIPELINE_COVERAGE_THRESHOLD, handles timeouts, and transitions overall run status.
Emits PIPELINE_RUN_STARTED and PIPELINE_RUN_FINISHED audit logs with zero student PII leakage.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db import collections as col
from app.pipeline.clock import get_clock
from app.pipeline.coverage import compute_stage_coverage, get_eligible_course_pids
from app.pipeline.stages import get_stage_handler
from app.pipeline.webhooks import dispatch_stage_ready_webhook
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event

logger = logging.getLogger("app.pipeline.advance")

TERMINAL_STAGE_STATUSES = frozenset({
    "complete",
    "partial",
    "timed_out",
    "skipped",
    "failed",
})

TERMINAL_RUN_STATUSES = frozenset({
    "complete",
    "partial",
    "failed",
})


async def advance_pipeline_run(
    db: AsyncIOMotorDatabase,
    run: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Advances the stages of a pipeline run according to dependency order and coverage thresholds.
    Updates the run in MongoDB col.PIPELINE_RUNS.
    """
    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    course_id = run["course_id"]
    week_index = run["week_index"]
    run_id = run["run_id"]
    initial_status = run.get("status", "pending")

    # If the run has already terminated, return as-is
    if initial_status in TERMINAL_RUN_STATUSES:
        return run

    # If run is pending, log PIPELINE_RUN_STARTED and mark running (scheduled runs only; manual trigger already logged PIPELINE_TRIGGERED)
    if initial_status == "pending":
        run["status"] = "running"
        if run.get("trigger") != "manual":
            try:
                await log_event(
                    request=None,
                    db=db,
                    action=AuditAction.PIPELINE_RUN_STARTED,
                    actor_id=run.get("triggered_by", "system:scheduler"),
                    actor_role="scheduler",
                    target_type="pipeline_run",
                    target_id=run_id,
                    outcome=AuditOutcome.SUCCESS,
                    details={"course_id": course_id, "week_index": week_index},
                )
            except Exception as exc:
                logger.warning("Failed to emit PIPELINE_RUN_STARTED audit log: %s", exc)

    # Pre-fetch eligible student PIDs for the course and week once
    eligible_pids: Set[str] = await get_eligible_course_pids(db, course_id, week_index)

    stages = run["stages"]

    # ── 1. LMS Aggregation Stage ───────────────────────────────────────────────
    st_agg = stages["lms_aggregation"]
    if st_agg["status"] == "waiting":
        handler = get_stage_handler("lms_aggregation")
        if handler is None:
            st_agg["status"] = "skipped"
            st_agg["note"] = "no handler registered"
            st_agg["coverage"] = 1.0
            st_agg["updated_at"] = now
        else:
            try:
                result = await handler(db, course_id, week_index)
                st_agg["status"] = result.get("status", "complete")
                st_agg["note"] = result.get("note")
                st_agg["coverage"] = 1.0
                st_agg["updated_at"] = now
            except Exception as exc:
                logger.exception("Stage 'lms_aggregation' failed for %s w%d", course_id, week_index)
                st_agg["status"] = "failed"
                st_agg["note"] = f"Aggregation failed: {type(exc).__name__}"
                st_agg["updated_at"] = now

    # If aggregation failed, run halts
    if st_agg["status"] == "failed":
        run["status"] = "failed"
        run["ended_at"] = now
        await _finalize_run(db, run, now)
        return run

    # ── 2. Signal C1 & C2 if LMS Aggregation is Done ──────────────────────────
    if st_agg["status"] in ("complete", "skipped"):
        for st_name in ("c1", "c2"):
            st = stages[st_name]
            if st["status"] == "waiting":
                st["status"] = "ready"
                st["since"] = now
                st["updated_at"] = now
                wh_res = await dispatch_stage_ready_webhook(st_name, course_id, week_index, run_id, now=now)
                if wh_res["notified"]:
                    st["notified_at"] = wh_res["notified_at"]
                st["notify_attempts"] = wh_res["attempts"]
                st["notify_error"] = wh_res["error"]

    # ── 3. Advance C1 & C2 Coverage and Timeout ───────────────────────────────
    for st_name in ("c1", "c2"):
        await _advance_component_stage(
            db=db,
            stage_dict=stages[st_name],
            stage_name=st_name,
            course_id=course_id,
            week_index=week_index,
            eligible_pids=eligible_pids,
            now=now,
        )

    # ── 4. Signal C3 if C1 and C2 Reached Terminal Status ──────────────────────
    c1_done = stages["c1"]["status"] in TERMINAL_STAGE_STATUSES
    c2_done = stages["c2"]["status"] in TERMINAL_STAGE_STATUSES

    if c1_done and c2_done:
        st_c3 = stages["c3"]
        if st_c3["status"] == "waiting":
            st_c3["status"] = "ready"
            st_c3["since"] = now
            st_c3["updated_at"] = now
            wh_res = await dispatch_stage_ready_webhook("c3", course_id, week_index, run_id, now=now)
            if wh_res["notified"]:
                st_c3["notified_at"] = wh_res["notified_at"]
            st_c3["notify_attempts"] = wh_res["attempts"]
            st_c3["notify_error"] = wh_res["error"]

    # ── 5. Advance C3 Coverage and Timeout ────────────────────────────────────
    await _advance_component_stage(
        db=db,
        stage_dict=stages["c3"],
        stage_name="c3",
        course_id=course_id,
        week_index=week_index,
        eligible_pids=eligible_pids,
        now=now,
    )

    # ── 6. Signal C4 if C3 Reached Terminal Status ────────────────────────────
    c3_done = stages["c3"]["status"] in TERMINAL_STAGE_STATUSES

    if c3_done:
        st_c4 = stages["c4"]
        if st_c4["status"] == "waiting":
            st_c4["status"] = "ready"
            st_c4["since"] = now
            st_c4["updated_at"] = now
            wh_res = await dispatch_stage_ready_webhook("c4", course_id, week_index, run_id, now=now)
            if wh_res["notified"]:
                st_c4["notified_at"] = wh_res["notified_at"]
            st_c4["notify_attempts"] = wh_res["attempts"]
            st_c4["notify_error"] = wh_res["error"]

    # ── 7. Advance C4 Coverage and Timeout ────────────────────────────────────
    await _advance_component_stage(
        db=db,
        stage_dict=stages["c4"],
        stage_name="c4",
        course_id=course_id,
        week_index=week_index,
        eligible_pids=eligible_pids,
        now=now,
    )

    # ── 8. Evaluate Overall Pipeline Run Status ───────────────────────────────
    all_terminal = all(st["status"] in TERMINAL_STAGE_STATUSES for st in stages.values())

    if all_terminal:
        all_success = all(st["status"] in ("complete", "skipped") for st in stages.values())
        all_failed = all(st["status"] == "failed" for st in stages.values())

        if all_success:
            run["status"] = "complete"
        elif all_failed:
            run["status"] = "failed"
        else:
            run["status"] = "partial"

        run["ended_at"] = now
        await _finalize_run(db, run, now)
    else:
        run["status"] = "running"
        await db[col.PIPELINE_RUNS].update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "status": run["status"],
                    "stages": run["stages"],
                    "ended_at": None,
                }
            },
        )

    return run


async def _advance_component_stage(
    db: AsyncIOMotorDatabase,
    stage_dict: Dict[str, Any],
    stage_name: str,
    course_id: str,
    week_index: int,
    eligible_pids: Set[str],
    now: datetime,
) -> None:
    """Evaluates coverage and timeouts for an active component stage."""
    current_status = stage_dict.get("status")

    if current_status not in ("ready", "receiving"):
        return

    cov = await compute_stage_coverage(
        db=db,
        stage=stage_name,
        course_id=course_id,
        week_index=week_index,
        eligible_pids=eligible_pids,
    )

    stage_dict["eligible"] = cov.eligible
    stage_dict["received"] = cov.received
    stage_dict["coverage"] = cov.coverage
    if cov.note:
        stage_dict["note"] = cov.note

    # C4 special case: 0 eligible students completes immediately
    if stage_name == "c4" and cov.eligible == 0:
        stage_dict["status"] = "complete"
        stage_dict["note"] = "no eligible students"
        stage_dict["updated_at"] = now
        return

    # Check coverage threshold
    if cov.coverage >= settings.PIPELINE_COVERAGE_THRESHOLD:
        stage_dict["status"] = "complete"
        stage_dict["updated_at"] = now
        return

    # Check timeout
    since_dt = stage_dict.get("since") or now
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=timezone.utc)

    elapsed_hours = (now - since_dt).total_seconds() / 3600.0

    if elapsed_hours >= settings.PIPELINE_STAGE_TIMEOUT_HOURS:
        if cov.received > 0:
            stage_dict["status"] = "partial"
        else:
            stage_dict["status"] = "timed_out"
        stage_dict["updated_at"] = now
        stage_dict["note"] = f"Stage timed out after {elapsed_hours:.1f} hours"
    elif cov.received > 0:
        stage_dict["status"] = "receiving"
        stage_dict["updated_at"] = now


async def _finalize_run(
    db: AsyncIOMotorDatabase,
    run: Dict[str, Any],
    now: datetime,
) -> None:
    """Persists terminal run state and records PIPELINE_RUN_FINISHED audit log."""
    await db[col.PIPELINE_RUNS].update_one(
        {"run_id": run["run_id"]},
        {
            "$set": {
                "status": run["status"],
                "stages": run["stages"],
                "ended_at": run["ended_at"],
            }
        },
    )

    try:
        outcome = AuditOutcome.SUCCESS if run["status"] == "complete" else AuditOutcome.FAILED
        await log_event(
            request=None,
            db=db,
            action=AuditAction.PIPELINE_RUN_FINISHED,
            actor_id=run.get("triggered_by", "system:scheduler"),
            actor_role="scheduler",
            target_type="pipeline_run",
            target_id=run["run_id"],
            outcome=outcome,
            details={
                "course_id": run["course_id"],
                "week_index": run["week_index"],
                "final_status": run["status"],
            },
        )
    except Exception as exc:
        logger.warning("Failed to emit PIPELINE_RUN_FINISHED audit log: %s", exc)
