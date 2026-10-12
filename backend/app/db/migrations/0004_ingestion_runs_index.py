"""
backend/app/db/migrations/0004_ingestion_runs_index.py

Feature 23: Component Ingestion Pipeline Indexes.
Ensures compound index on (component, started_at desc) for 'ingestion_runs'
collection so component run monitoring and audit queries are fully indexed.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from scripts.setup_db import setup_database

MIGRATION_ID = "0004_ingestion_runs_index"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies updated collection indexes using setup_database.
    """
    db_name = db.name
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
