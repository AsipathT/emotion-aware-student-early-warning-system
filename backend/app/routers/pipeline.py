"""
backend/app/routers/pipeline.py

Feature 22: Pipeline Trigger & Scheduler Management Endpoints.
Provides manual execution triggers and scheduler observability for platform administrators.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.db import collections as col
from app.jobs.scheduler import get_scheduler_status
from app.jobs.weekly_aggregation import run_weekly_pipeline
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post(
    "/trigger-weekly",
    summary="Manually Trigger Weekly Aggregation Pipeline",
    description="Executes telemetry aggregation (col.BEHAVIOR_WEEKLY) and academic record derivation.",
    status_code=status.HTTP_200_OK,
)
async def trigger_weekly_pipeline(
    request: Request,
    course_id: Optional[str] = Query(None, description="Optional target course identifier (processes all if omitted)"),
    week_index: Optional[int] = Query(None, ge=0, description="Optional academic week index (defaults to 1)"),
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        results = await run_weekly_pipeline(
            db=db,
            course_id=course_id,
            week_index=week_index,
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=admin.id,
            actor_role=admin.role.value if hasattr(admin.role, "value") else str(admin.role),
            target_type="weekly_pipeline",
            target_id=results.get("run_id"),
            outcome=AuditOutcome.SUCCESS,
            details={
                "course_id": course_id,
                "week_index": week_index,
                "records_processed": results.get("behavior_records_created", 0),
            },
        )
        return {
            "status": "success",
            "message": "Weekly aggregation pipeline completed successfully.",
            "data": results,
        }
    except Exception as exc:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=admin.id,
            actor_role=admin.role.value if hasattr(admin.role, "value") else str(admin.role),
            target_type="weekly_pipeline",
            target_id="failed",
            outcome=AuditOutcome.FAILED,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Weekly pipeline execution failed: {exc}",
        )


@router.get(
    "/status",
    summary="Get Pipeline Scheduler Status",
    description="Returns current state of background scheduler and latest pipeline execution details.",
)
async def get_pipeline_status(
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    scheduler_info = get_scheduler_status()

    # Query latest weekly pipeline run from col.INGESTION_RUNS
    latest_run = await db[col.INGESTION_RUNS].find_one(
        {"component": "weekly_pipeline"},
        {"_id": 0},
        sort=[("started_at", -1)],
    )

    return {
        "scheduler": scheduler_info,
        "latest_execution": latest_run,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
