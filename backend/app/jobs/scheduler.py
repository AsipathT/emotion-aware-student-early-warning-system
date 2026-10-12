"""
backend/app/jobs/scheduler.py

Feature 22: Background APScheduler Service.
Provides lifecycle management for periodic automated pipeline execution.
"""

import logging
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import db
from app.jobs.weekly_aggregation import run_weekly_pipeline

logger = logging.getLogger("app.jobs.scheduler")

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    global _scheduler
    return _scheduler


async def _scheduled_pipeline_job():
    logger.info("[Scheduler] Triggering periodic weekly aggregation pipeline...")
    try:
        results = await run_weekly_pipeline(db=db)
        logger.info(f"[Scheduler] Pipeline completed successfully: {results}")
    except Exception as exc:
        logger.error(f"[Scheduler] Pipeline job failed: {exc}")


def start_scheduler() -> None:
    """Initializes and starts the AsyncIOScheduler background worker."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    # Default schedule: Every Sunday at midnight UTC (00:00)
    _scheduler.add_job(
        _scheduled_pipeline_job,
        trigger=CronTrigger(day_of_week="sun", hour=0, minute=0, timezone="UTC"),
        id="weekly_lms_aggregation",
        name="Weekly LMS Telemetry & Academic Aggregation",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("[Scheduler] APScheduler background engine started.")


def stop_scheduler() -> None:
    """Gracefully shuts down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped.")
        _scheduler = None


def get_scheduler_status() -> Dict[str, Any]:
    """Returns runtime state and next execution timing."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {
            "is_running": False,
            "jobs_count": 0,
            "next_run_time": None,
        }

    job = _scheduler.get_job("weekly_lms_aggregation")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "is_running": True,
        "jobs_count": len(_scheduler.get_jobs()),
        "next_run_time": next_run,
    }
