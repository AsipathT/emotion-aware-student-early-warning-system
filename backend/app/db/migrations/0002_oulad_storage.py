"""
backend/app/db/migrations/0002_oulad_storage.py

Feature 26: OULAD Storage & Index Migration.
Updates $jsonSchema validators across touched collections for OULAD provenance
(source, ingestion_run_id) and imported ground truth fields.
Migrates the grades unique index to (pid, course_id, assessment_id) to support
multiple assessments in the same academic week.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import OperationFailure
from scripts.setup_db import setup_database

MIGRATION_ID = "0002_oulad_storage"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies updated collection validators and ensures the grades collection
    index accommodates multiple assessments per week.
    """
    db_name = db.name

    # 1. Safely drop legacy unique weekly index on grades if present
    try:
        existing_indexes = await db.grades.index_information()
        if "idx_grades_compound_weekly_unique" in existing_indexes:
            await db.grades.drop_index("idx_grades_compound_weekly_unique")
            print("  [-] Dropped legacy index 'idx_grades_compound_weekly_unique' on grades.")
    except (OperationFailure, Exception) as exc:
        # Collection might not exist or index might already be dropped
        pass

    # 2. Invoke setup_database to apply updated validators and create indexes
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
