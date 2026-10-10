"""
backend/app/db/migrations/0001_init.py

Initial schema migration: invokes the idempotent database setup logic,
creating all collections, strict $jsonSchema validators, and indexes.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from scripts.setup_db import setup_database

MIGRATION_ID = "0001_init"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies the initial collection structure, validators, and indexes.
    Idempotent operation.
    """
    db_name = db.name
    # Pass db_name so setup applies directly to the target database
    await setup_database(db_name=db_name, dry_run=False, check_only=False)
