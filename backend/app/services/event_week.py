"""
backend/app/services/event_week.py

Academic week resolution for live telemetry and activity events.
Provides crash-safe resolution delegating to get_week_index.
"""

from datetime import datetime
from typing import Any, Optional

from app.services.week_index import get_week_index


async def resolve_event_week(
    db: Any,
    course_id: Optional[str],
    ts: Optional[datetime],
    fallback: int,
) -> int:
    """
    Resolves the academic week_index for an activity event.
    If course_id is falsy, returns fallback.
    Otherwise attempts to compute week index via get_week_index, returning fallback on error.
    """
    if not course_id:
        return fallback
    try:
        return await get_week_index(db, str(course_id), ts)
    except Exception:
        return fallback
