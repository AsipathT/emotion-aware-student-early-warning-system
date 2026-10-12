"""
backend/app/pipeline/scheduler.py

APScheduler integration for Feature 22: Weekly scheduler / pipeline orchestrator.
Manages background periodic execution of pipeline ticks every SCHEDULER_TICK_MINUTES.
Scheduler is inactive by default (SCHEDULER_ENABLED=false) and disabled in test suites.
"""

import logging
import os
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import db
from app.pipeline.orchestrator import run_pipeline_tick

logger = logging.getLogger("app.pipeline.scheduler")

_scheduler: Optional[AsyncIOScheduler] = None


def get_pipeline_scheduler() -> Optional[AsyncIOScheduler]:
    """Returns the global AsyncIOScheduler instance, if initialized."""
    global _scheduler
    return _scheduler


async def _scheduled_pipeline_job() -> None:
    """Invoked periodically by APScheduler to execute the orchestrator tick."""
    logger.info("Scheduler triggering periodic pipeline tick...")
    try:
        result = await run_pipeline_tick(db=db)
        logger.info("Periodic pipeline tick completed: %s", result.get("status"))
    except Exception as exc:
        logger.exception("Periodic pipeline tick failed: %s", exc)


def start_pipeline_scheduler() -> None:
    """
    Initializes and starts the AsyncIOScheduler background worker if enabled.
    Guarded against running during automated tests.
    """
    global _scheduler

    if os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("Pipeline scheduler skipped in test environment.")
        return

    if not settings.SCHEDULER_ENABLED:
        logger.info("Pipeline scheduler is disabled (SCHEDULER_ENABLED=false).")
        return

    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    interval_minutes = max(1, settings.SCHEDULER_TICK_MINUTES)

    _scheduler.add_job(
        _scheduled_pipeline_job,
        trigger=IntervalTrigger(minutes=interval_minutes, timezone="UTC"),
        id="pipeline_tick_job",
        name="Feature 22 Weekly Pipeline Tick",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Feature 22 Pipeline scheduler started with %d-minute interval.", interval_minutes)


def stop_pipeline_scheduler() -> None:
    """Gracefully shuts down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Feature 22 Pipeline scheduler stopped.")
        _scheduler = None


def get_pipeline_scheduler_status() -> Dict[str, Any]:
    """Returns runtime state and next execution timing for diagnostics and admin endpoints."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {
            "is_running": False,
            "jobs_count": 0,
            "next_run_time": None,
            "tick_minutes": settings.SCHEDULER_TICK_MINUTES,
            "enabled": settings.SCHEDULER_ENABLED,
        }

    job = _scheduler.get_job("pipeline_tick_job")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "is_running": True,
        "jobs_count": len(_scheduler.get_jobs()),
        "next_run_time": next_run,
        "tick_minutes": settings.SCHEDULER_TICK_MINUTES,
        "enabled": settings.SCHEDULER_ENABLED,
    }
