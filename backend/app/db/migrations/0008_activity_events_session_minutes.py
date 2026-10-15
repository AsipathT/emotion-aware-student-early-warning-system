"""
backend/app/db/migrations/0008_activity_events_session_minutes.py

Feature 22/25: Update activity_events schema validator to accept session_minutes.
Uses collMod to safely and idempotently update the $jsonSchema validator
on the 'activity_events' collection so telemetry records with session_minutes
pass MongoDB engine-level schema validation.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import collections as col
from app.db.storage_models import ActivityEventStorage
from app.db.validators import generate_mongo_schema

MIGRATION_ID = "0008_activity_events_session_minutes"


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies the updated $jsonSchema validator to the activity_events collection
    using collMod, or creates the collection if it does not yet exist.
    """
    validator = generate_mongo_schema(ActivityEventStorage)
    existing_cols = await db.list_collection_names()

    if col.ACTIVITY_EVENTS in existing_cols:
        await db.command(
            "collMod",
            col.ACTIVITY_EVENTS,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        await db.create_collection(
            col.ACTIVITY_EVENTS,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
