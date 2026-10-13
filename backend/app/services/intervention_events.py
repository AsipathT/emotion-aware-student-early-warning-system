"""
backend/app/services/intervention_events.py

Feature 34: Asynchronous Intervention Event Hooks.
Defines non-blocking, exception-safe event hook callbacks triggered
during intervention lifecycle transitions.

Hook reservations:
  - on_intervention_offered: Reserved for Feature 37 (Student Notification Dispatch).
  - on_intervention_completed: Reserved for Feature 39 (Student Experience Feedback Survey).

Invariants:
  - Must be NO-OP stubs for Feature 34.
  - Callers must execute these hooks inside try/except blocks so failures never break
    the primary transaction or HTTP response.
"""

import logging
from typing import Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("app.intervention_events")


async def on_intervention_offered(
    db: AsyncIOMotorDatabase,
    record: Dict[str, Any],
) -> None:
    """
    Hook triggered when an intervention transitions to 'offered'.
    F34: NO-OP stub logging event occurrence.
    F37: Will trigger multi-channel student notification dispatch.
    """
    interv_id = record.get("id") or record.get("intervention_id")
    pid = record.get("pid")
    logger.info(
        "[HOOK: on_intervention_offered] Intervention '%s' offered to student '%s'. (F37 dispatch pending)",
        interv_id,
        pid,
    )


async def on_intervention_completed(
    db: AsyncIOMotorDatabase,
    record: Dict[str, Any],
) -> None:
    """
    Hook triggered when an intervention transitions to 'completed'.
    F34: NO-OP stub logging event occurrence.
    F39: Will initiate student feedback survey and reflective evaluation.
    """
    interv_id = record.get("id") or record.get("intervention_id")
    pid = record.get("pid")
    logger.info(
        "[HOOK: on_intervention_completed] Intervention '%s' completed for student '%s'. (F39 survey pending)",
        interv_id,
        pid,
    )
