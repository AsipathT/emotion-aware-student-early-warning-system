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
    F37: Dispatches supportive student notification without revealing analytics.
    """
    try:
        interv_id = str(record.get("id") or record.get("intervention_id") or "")
        pid = str(record.get("pid") or "")
        if not pid:
            return

        from app.services.intervention_catalog import get_entry
        from app.services.notification_service import notify_pid

        itype = record.get("intervention_type")
        catalog_entry = get_entry(itype)
        student_label = catalog_entry.get("student_label") or "Academic Guidance & Support"

        # Derive n = number of entries with status == "offered" in the record's status_history
        status_history = record.get("status_history") or []
        n = sum(1 for entry in status_history if str(entry.get("status", "")).strip().lower() == "offered")
        if n == 0:
            n = 1

        await notify_pid(
            db=db,
            pid=pid,
            template_key="support_offered",
            student_label=student_label,
            link="/support",
            related_id=interv_id,
            dedupe_key=f"support_offered:{interv_id}:{n}",
        )
        logger.info(
            "[HOOK: on_intervention_offered] Notification dispatched for intervention '%s', student '%s' (offer #%d).",
            interv_id,
            pid,
            n,
        )
    except Exception as exc:
        logger.warning("[HOOK: on_intervention_offered] Failed to dispatch notification: %s", exc)


async def on_intervention_completed(
    db: AsyncIOMotorDatabase,
    record: Dict[str, Any],
) -> None:
    """
    Hook triggered when an intervention transitions to 'completed'.
    F39: Dispatches supportive feedback request notification to the student.
    """
    try:
        interv_id = str(record.get("id") or record.get("intervention_id") or "")
        pid = str(record.get("pid") or "")
        if not pid:
            return

        from app.services.notification_service import notify_pid

        # Derive n = number of entries with status == "completed" in status_history
        status_history = record.get("status_history") or []
        n = sum(1 for entry in status_history if str(entry.get("status", "")).strip().lower() == "completed")
        if n == 0:
            n = 1

        await notify_pid(
            db=db,
            pid=pid,
            template_key="feedback_request",
            link="/support",
            related_id=interv_id,
            dedupe_key=f"feedback_request:{interv_id}:{n}",
        )
        logger.info(
            "[HOOK: on_intervention_completed] Feedback request notification dispatched for intervention '%s', student '%s' (completion #%d).",
            interv_id,
            pid,
            n,
        )
    except Exception as exc:
        logger.warning("[HOOK: on_intervention_completed] Failed to dispatch feedback request notification: %s", exc)

