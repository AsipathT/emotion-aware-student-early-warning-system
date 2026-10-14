"""
backend/app/services/week_index.py

Academic week index calculation for LMS courses.

Temporary fallback until the platform defines a course calendar for LMS-created courses (see Niduka); swap implementation here only.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import collections as col


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise datetime to UTC-aware (handling Motor naive datetimes)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_week_index(
    ts: Optional[datetime],
    course_week_docs: Optional[List[Dict[str, Any]]],
    course_created_at: Optional[datetime],
) -> int:
    """
    Pure function to determine academic week_index (0-based) for a timestamp.

    Rule:
    1. Normalise ts and created_at to UTC-aware (Motor returns NAIVE UTC datetimes).
    2. If a course_weeks document has start_date <= ts <= end_date (normalise those too),
       return its week_index.
    3. Otherwise fallback: max(0, (ts - course_created_at).days // 7), the same
       floor-by-7-days convention as the OULAD importer day_to_week.
    4. If course_created_at is missing, return 0.
    """
    ts_utc = _ensure_utc(ts) or datetime.now(timezone.utc)

    if course_week_docs:
        for w in course_week_docs:
            s_date = _ensure_utc(w.get("start_date"))
            e_date = _ensure_utc(w.get("end_date"))
            w_idx = w.get("week_index")
            if s_date is not None and e_date is not None and w_idx is not None:
                if s_date <= ts_utc <= e_date:
                    return max(0, int(w_idx))

    # Fallback to course created_at offset
    created_utc = _ensure_utc(course_created_at)
    if created_utc is None:
        return 0

    delta_days = (ts_utc - created_utc).days
    return max(0, delta_days // 7)


async def get_week_index(
    db: AsyncIOMotorDatabase,
    course_id: str,
    ts: Optional[datetime] = None,
) -> int:
    """
    Async helper that loads course_weeks and course created_at from MongoDB
    and delegates to compute_week_index.
    """
    if ts is None:
        ts = datetime.now(timezone.utc)

    cid_str = str(course_id).strip()

    try:
        # Load course_weeks for the course
        cursor = db[col.COURSE_WEEKS].find(
            {"course_id": cid_str},
            {"week_index": 1, "start_date": 1, "end_date": 1, "_id": 0},
        ).sort("week_index", 1)
        course_week_docs = await cursor.to_list(length=1000)

        # Lookup course by _id then id
        course_doc = await db[col.COURSES].find_one({"_id": cid_str}, {"created_at": 1})
        if not course_doc:
            course_doc = await db[col.COURSES].find_one({"id": cid_str}, {"created_at": 1})

        course_created_at = course_doc.get("created_at") if course_doc else None

        return compute_week_index(ts, course_week_docs, course_created_at)
    except Exception:
        return 0
