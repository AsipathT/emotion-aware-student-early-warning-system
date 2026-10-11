"""
backend/app/db/migrations/0003_export_indexes.py

Feature 21: Component Export Query Optimization Indexes.
Ensures compound indexes on (course_id, week_index) for 'messages' and
'behavior_weekly' collections so component export queries are fully indexed.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from scripts.setup_db import setup_database

MIGRATION_ID = "0003_export_indexes"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies updated collection indexes using setup_database.
    """
    db_name = db.name
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
