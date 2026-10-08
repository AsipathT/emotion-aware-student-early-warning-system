import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.services.aggregation import compute_weekly_features

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def weekly_aggregation_job():
    """Job to run the weekly aggregation service."""
    logger.info("Starting weekly aggregation job...")
    try:
        async with AsyncSessionLocal() as db:
            count = await compute_weekly_features(db)
            await db.commit()
            logger.info(f"Weekly aggregation completed. Upserted {count} records.")
    except Exception as e:
        logger.error(f"Error in weekly aggregation job: {e}")


def start_scheduler():
    """Start the APScheduler if ENABLE_SCHEDULER is True."""
    import os
    enable_scheduler = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
    
    if not enable_scheduler:
        logger.info("Scheduler is disabled via ENABLE_SCHEDULER env var.")
        return

    # Run every Sunday at 00:00 UTC
    scheduler.add_job(
        weekly_aggregation_job,
        trigger=CronTrigger(day_of_week="sun", hour=0, minute=0),
        id="weekly_aggregation",
        name="Weekly Feature Aggregation",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Scheduler started.")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
