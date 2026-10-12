"""
backend/app/db/migrations/0005_readback_export_indexes.py

Read-Back Export Endpoints: Query Optimization Indexes.
Adds compound indexes on (course_id, week_index) for affective_weekly and
engagement_trajectories, plus ingested_at indexes across export and read-back collections.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from scripts.setup_db import setup_database

MIGRATION_ID = "0005_readback_export_indexes"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies updated collection indexes using setup_database.
    """
    db_name = db.name
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
