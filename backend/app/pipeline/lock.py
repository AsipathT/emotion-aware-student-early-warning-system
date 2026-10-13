"""
backend/app/pipeline/lock.py

Distributed atomic scheduler lock using MongoDB 'scheduler_locks' collection.
Ensures only one worker instance processes a pipeline tick at a time.
Supports custom lock keys and expiration takeover.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.db import collections as col
from app.pipeline.clock import get_clock

DEFAULT_LOCK_ID = "weekly_pipeline"


async def acquire_lock(
    db: AsyncIOMotorDatabase,
    owner: Optional[str] = None,
    lease_seconds: int = 300,
    now: Optional[datetime] = None,
    key: str = DEFAULT_LOCK_ID,
    owner_id: Optional[str] = None,
) -> bool:
    """
    Attempts to atomically acquire or renew the distributed pipeline lock.
    Succeeds if:
    1. Lock document does not exist, or
    2. Existing lock lease has expired (expires_at <= now), or
    3. Existing lock is already owned by this owner.
    """
    lock_owner = owner or owner_id or "default_worker"
    lock_id = key

    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    expires_at = now + timedelta(seconds=lease_seconds)

    # 1. Attempt to update an existing expired or self-owned lock
    result = await db[col.SCHEDULER_LOCKS].update_one(
        {
            "_id": lock_id,
            "$or": [
                {"expires_at": {"$lte": now}},
                {"owner": lock_owner},
            ],
        },
        {
            "$set": {
                "owner": lock_owner,
                "acquired_at": now,
                "expires_at": expires_at,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
    )

    if result.matched_count > 0:
        return True

    # 2. If lock document was absent, attempt atomic insertion
    try:
        await db[col.SCHEDULER_LOCKS].insert_one({
            "_id": lock_id,
            "owner": lock_owner,
            "acquired_at": now,
            "expires_at": expires_at,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })
        return True
    except DuplicateKeyError:
        # Document was inserted by another concurrent worker between update and insert
        return False
    except Exception:
        return False


async def heartbeat_lock(
    db: AsyncIOMotorDatabase,
    owner: Optional[str] = None,
    lease_seconds: int = 300,
    now: Optional[datetime] = None,
    key: str = DEFAULT_LOCK_ID,
    owner_id: Optional[str] = None,
) -> bool:
    """Extends the lease of an actively held lock."""
    lock_owner = owner or owner_id or "default_worker"
    lock_id = key

    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    expires_at = now + timedelta(seconds=lease_seconds)
    result = await db[col.SCHEDULER_LOCKS].update_one(
        {"_id": lock_id, "owner": lock_owner},
        {"$set": {"expires_at": expires_at}},
    )
    return result.matched_count > 0


async def release_lock(
    db: AsyncIOMotorDatabase,
    owner: Optional[str] = None,
    key: str = DEFAULT_LOCK_ID,
    owner_id: Optional[str] = None,
) -> bool:
    """Releases the lock held by this owner."""
    lock_owner = owner or owner_id or "default_worker"
    lock_id = key

    result = await db[col.SCHEDULER_LOCKS].delete_one({"_id": lock_id, "owner": lock_owner})
    return result.deleted_count > 0
