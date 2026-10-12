"""
backend/app/pipeline/stages.py

Stage handler registry for pipeline execution.
Registers handlers for pipeline stages (e.g. lms_aggregation).
Handler exceptions mark the stage 'failed' with a sanitized note without crashing the tick.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("app.pipeline.stages")

# Registry mapping stage name -> async callable(db, course_id, week_index) -> dict
_STAGE_HANDLERS: Dict[str, Callable[[AsyncIOMotorDatabase, str, int], Awaitable[Dict[str, Any]]]] = {}


def register_stage_handler(
    name: str,
    handler: Callable[[AsyncIOMotorDatabase, str, int], Awaitable[Dict[str, Any]]],
) -> None:
    """Registers an asynchronous handler for a named pipeline stage."""
    _STAGE_HANDLERS[name] = handler


def get_stage_handler(
    name: str,
) -> Optional[Callable[[AsyncIOMotorDatabase, str, int], Awaitable[Dict[str, Any]]]]:
    """Retrieves the registered handler for a named stage, if any."""
    return _STAGE_HANDLERS.get(name)


def clear_stage_handlers() -> None:
    """Clears all registered handlers (used in testing)."""
    _STAGE_HANDLERS.clear()


# ── Feature 20 Default Hook / Fallback ────────────────────────────────────────

async def default_lms_aggregation_handler(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
) -> Dict[str, Any]:
    """
    Default handler for 'lms_aggregation'.
    Invokes Feature 20 weekly aggregation if available, or marks stage skipped.
    """
    try:
        from app.jobs.weekly_aggregation import aggregate_weekly_behavior
        records = await aggregate_weekly_behavior(db=db, course_id=course_id, week_index=week_index)
        return {
            "status": "complete",
            "records_created": records,
            "note": f"Feature 20 aggregation completed ({records} records created)",
        }
    except (ImportError, AttributeError):
        return {
            "status": "skipped",
            "note": "no weekly aggregation registered (Feature 20)",
        }


# Register default handler at module import
register_stage_handler("lms_aggregation", default_lms_aggregation_handler)
