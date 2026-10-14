"""
backend/app/services/intervention_service.py

Feature 34: Intervention Lifecycle Management Service.
Provides centralized state transition logic, validation against the Human-in-the-Loop
lifecycle graph (ALLOWED_TRANSITIONS), and synchronized persistence across
operational `intervention_records` and canonical `interventions`.

REUSED by:
  - F34: Staff intervention management (offered, in_progress, cancelled)
  - F35: Outcome resolution (in_progress -> completed)
  - F38: Student interactive actions (offered -> accepted / declined)
  - F39: Final evaluation and closure
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import collections as col
from app.models.intervention_record import (
    ALLOWED_TRANSITIONS,
    COL_INTERVENTION_RECORDS,
    can_transition,
)

logger = logging.getLogger("app.intervention_service")


async def change_status(
    db: AsyncIOMotorDatabase,
    record: Dict[str, Any],
    new_status: str,
    actor_id: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a validated lifecycle status transition for an intervention.

    Invariants enforced:
      1. Must comply with ALLOWED_TRANSITIONS graph (raises HTTP 409 Conflict otherwise).
      2. Appends immutable entry to status_history with timestamp and actor attribution.
      3. Updates operational `intervention_records` state.
      4. Updates canonical `interventions` document via strict $set status only, preserving contract fields.
      5. Returns the refreshed operational record document.
    """
    interv_id = str(record.get("id") or record.get("_id") or record.get("intervention_id")).strip()
    current_status = str(record.get("status", "")).strip().lower()
    target_status = str(new_status).strip().lower()

    # 1. State machine transition check
    if not can_transition(current_status, target_status):
        allowed_targets = ALLOWED_TRANSITIONS.get(current_status, [])
        logger.warning(
            "Illegal intervention lifecycle jump rejected: '%s' -> '%s' (intervention_id=%s, allowed=%s)",
            current_status,
            target_status,
            interv_id,
            allowed_targets,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid lifecycle transition from '{current_status}' to '{target_status}'. "
                f"Permissible target states from current state: {allowed_targets}."
            ),
        )

    now_utc = datetime.now(timezone.utc)
    new_history_entry = {
        "status": target_status,
        "at": now_utc,
        "by": str(actor_id),
        "note": str(note).strip() if note else None,
    }

    # 2. Update operational record in `intervention_records`
    update_res = await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": interv_id}, {"_id": interv_id}]},
        {
            "$set": {
                "status": target_status,
                "updated_at": now_utc,
            },
            "$push": {
                "status_history": new_history_entry,
            },
        },
    )

    if update_res.matched_count == 0:
        logger.error("Failed to locate intervention record '%s' during status transition", interv_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{interv_id}' not found.",
        )

    # 3. Synchronize canonical `interventions` document status strictly via $set status
    canon_update = await db[col.INTERVENTIONS].update_one(
        {"$or": [{"intervention_id": interv_id}, {"_id": interv_id}]},
        {
            "$set": {
                "status": target_status,
            }
        },
    )

    if canon_update.matched_count == 0:
        logger.warning(
            "Canonical intervention '%s' not found for status synchronization; operational record updated.",
            interv_id,
        )

    # 4. Return refreshed document
    updated_doc = await db[COL_INTERVENTION_RECORDS].find_one(
        {"$or": [{"id": interv_id}, {"_id": interv_id}]}
    )
    return updated_doc or record
