"""
backend/app/db/migrations/0006_feature22_pipeline_orchestrator.py

Feature 22: Pipeline Orchestrator and Scheduler Lock Collections.
Creates 'pipeline_runs' and 'scheduler_locks' collections with strict JSON schemas
and unique compound indexes.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from scripts.setup_db import setup_database

MIGRATION_ID = "0006_feature22_pipeline_orchestrator"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies updated collection schemas and indexes using setup_database.
    """
    db_name = db.name
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
