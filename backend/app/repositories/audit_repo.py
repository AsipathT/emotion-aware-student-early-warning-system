"""
backend/app/repositories/audit_repo.py

Feature 7: Immutable, Append-Only Audit Log Repository.
Enforces:
  - Strictly append-only: ONLY insert_one and query/find methods.
  - No update, replace, or delete methods exist.
  - Startup index management for timestamp (descending), actor_id, target_id, and action.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.audit import AuditLogBase


async def insert_audit_log(
    db: AsyncIOMotorDatabase,
    log_entry: AuditLogBase,
) -> str:
    """
    Inserts a single audit log record into the immutable MongoDB 'audit_logs' collection.
    Append-only operation.
    """
    doc = log_entry.model_dump(by_alias=True)
    doc["_id"] = log_entry.id
    # Ensure datetime object is stored directly in Mongo
    doc["timestamp"] = log_entry.timestamp

    await db.audit_logs.insert_one(doc)
    return str(doc["_id"])


async def find_audit_logs_paginated(
    db: AsyncIOMotorDatabase,
    query: Dict[str, Any],
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Finds audit records matching filter criteria, sorted by timestamp descending.
    Returns (records, total_count).
    """
    total = await db.audit_logs.count_documents(query)
    cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    records = await cursor.to_list(length=limit)
    return records, total


async def stream_audit_logs(
    db: AsyncIOMotorDatabase,
    query: Dict[str, Any],
    limit: int = 5000,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Asynchronous generator streaming audit records for CSV export.
    Enforces a strict upper bound cap on rows.
    """
    cursor = db.audit_logs.find(query).sort("timestamp", -1).limit(limit)
    async for doc in cursor:
        yield doc


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Ensures optimal indexing on the audit_logs collection at application startup.
    Indexes:
      - timestamp (descending) for chronological queries
      - actor_id for investigator lookups
      - target_id for subject queries
      - action for audit filtering
    """
    await db.audit_logs.create_index([("timestamp", -1)], name="idx_audit_timestamp_desc")
    await db.audit_logs.create_index([("actor_id", 1)], name="idx_audit_actor_id")
    await db.audit_logs.create_index([("target_id", 1)], name="idx_audit_target_id")
    await db.audit_logs.create_index([("action", 1)], name="idx_audit_action")
