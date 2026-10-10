"""
backend/app/services/audit.py

Feature 7: Audit Logging Service.
Records immutable audit logs to MongoDB 'audit_logs' for security, compliance,
and tracking sensitive actions like student pseudonym identity reveal.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


async def log_audit_event(
    db: AsyncIOMotorDatabase,
    action: str,
    requester_id: str,
    target_pid: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Records an audit log event into MongoDB 'audit_logs' collection.

    Parameters:
      db: Motor database instance.
      action: Event action name, e.g. "IDENTITY_REVEAL".
      requester_id: User UUID of the actor initiating the request.
      target_pid: Pseudonym ID affected by this action.
      details: Additional contextual metadata.
    """
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())

    log_doc = {
        "_id": event_id,
        "id": event_id,
        "action": action,
        "requester_id": str(requester_id),
        "target_pid": target_pid,
        "details": details or {},
        "timestamp": now,
    }

    await db.audit_logs.insert_one(log_doc)
    return log_doc
