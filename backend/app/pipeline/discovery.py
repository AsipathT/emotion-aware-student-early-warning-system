"""
backend/app/pipeline/discovery.py

Due week discovery and run creation for the weekly pipeline orchestrator.
Identifies finished academic course weeks past the grace threshold and
initializes new pipeline_runs documents with duplicate-key safety.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db import collections as col
from app.pipeline.clock import get_clock


async def find_due_weeks(
    db: AsyncIOMotorDatabase,
    now: Optional[datetime] = None,
    grace_hours: Optional[int] = None,
    lookback_weeks: Optional[int] = None,
    max_weeks: Optional[int] = None,
    excluded_sources: Optional[List[str]] = None,
    target_course_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Finds finished course_weeks that are ready for pipeline execution:
    1. end_date <= now - grace_hours
    2. end_date >= now - lookback_weeks
    3. Course source not in excluded_sources (e.g. 'oulad', 'demo')
    4. No pipeline_runs document exists for (course_id, week_index)
    5. Sorted oldest first, capped at max_weeks.
    """
    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if grace_hours is None:
        grace_hours = settings.SCHEDULER_GRACE_HOURS
    if lookback_weeks is None:
        lookback_weeks = settings.SCHEDULER_LOOKBACK_WEEKS
    if max_weeks is None:
        max_weeks = settings.SCHEDULER_MAX_WEEKS_PER_TICK
    if excluded_sources is None:
        excluded_sources = settings.SCHEDULER_EXCLUDED_COURSE_SOURCES

    cutoff_grace = now - timedelta(hours=grace_hours)
    cutoff_lookback = now - timedelta(weeks=lookback_weeks)

    # 1. Identify excluded courses
    excluded_course_ids: Set[str] = set()
    if excluded_sources:
        ex_query: Dict[str, Any] = {"source": {"$in": [s.lower() for s in excluded_sources]}}
        cursor = db[col.COURSES].find(ex_query, {"course_id": 1, "_id": 0})
        excluded_course_ids = {c["course_id"] async for c in cursor if c.get("course_id")}

    # 2. Query course_weeks within the valid lookback and grace time window
    cw_query: Dict[str, Any] = {
        "end_date": {"$lte": cutoff_grace, "$gte": cutoff_lookback},
    }
    if target_course_id:
        cw_query["course_id"] = target_course_id
    elif excluded_course_ids:
        cw_query["course_id"] = {"$nin": list(excluded_course_ids)}

    candidates_cursor = db[col.COURSE_WEEKS].find(cw_query).sort([("end_date", 1)])
    candidates = await candidates_cursor.to_list(length=max_weeks * 5)

    if not candidates:
        return []

    # 3. Filter out course weeks that already have a pipeline_runs record
    pairs = [{"course_id": cw["course_id"], "week_index": cw["week_index"]} for cw in candidates]
    existing_cursor = db[col.PIPELINE_RUNS].find(
        {"$or": pairs},
        {"course_id": 1, "week_index": 1, "_id": 0},
    )
    existing_set = {(r["course_id"], r["week_index"]) async for r in existing_cursor}

    due_weeks: List[Dict[str, Any]] = []
    for cw in candidates:
        pair_key = (cw["course_id"], cw["week_index"])
        if pair_key not in existing_set:
            due_weeks.append(cw)
            if len(due_weeks) >= max_weeks:
                break

    return due_weeks


async def create_pipeline_run(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
    week_end: datetime,
    trigger: str = "scheduler",
    triggered_by: str = "system:scheduler",
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """
    Creates and persists a new pipeline_runs document for (course_id, week_index).
    Returns the created document, or None if a duplicate key conflict occurs.
    """
    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if week_end.tzinfo is None:
        week_end = week_end.replace(tzinfo=timezone.utc)

    run_id = f"run_{course_id}_w{week_index}_{uuid.uuid4().hex[:8]}"

    initial_stages: Dict[str, Dict[str, Any]] = {
        "lms_aggregation": {
            "status": "waiting",
            "since": now,
            "updated_at": now,
            "note": None,
            "coverage": None,
            "eligible": 0,
            "received": 0,
            "notified_at": None,
            "notify_attempts": 0,
            "notify_error": None,
        },
        "c1": {
            "status": "waiting",
            "since": now,
            "updated_at": now,
            "note": None,
            "coverage": None,
            "eligible": 0,
            "received": 0,
            "notified_at": None,
            "notify_attempts": 0,
            "notify_error": None,
        },
        "c2": {
            "status": "waiting",
            "since": now,
            "updated_at": now,
            "note": None,
            "coverage": None,
            "eligible": 0,
            "received": 0,
            "notified_at": None,
            "notify_attempts": 0,
            "notify_error": None,
        },
        "c3": {
            "status": "waiting",
            "since": now,
            "updated_at": now,
            "note": None,
            "coverage": None,
            "eligible": 0,
            "received": 0,
            "notified_at": None,
            "notify_attempts": 0,
            "notify_error": None,
        },
        "c4": {
            "status": "waiting",
            "since": now,
            "updated_at": now,
            "note": None,
            "coverage": None,
            "eligible": 0,
            "received": 0,
            "notified_at": None,
            "notify_attempts": 0,
            "notify_error": None,
        },
    }

    doc: Dict[str, Any] = {
        "_id": f"pipe_{course_id}_{week_index}",
        "run_id": run_id,
        "course_id": course_id,
        "week_index": week_index,
        "week_end": week_end,
        "status": "pending",
        "trigger": trigger,
        "triggered_by": triggered_by,
        "started_at": now,
        "ended_at": None,
        "stages": initial_stages,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }

    try:
        await db[col.PIPELINE_RUNS].insert_one(doc)
        return doc
    except DuplicateKeyError:
        # A run already exists for this (course_id, week_index)
        return None
