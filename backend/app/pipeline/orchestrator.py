"""
backend/app/pipeline/orchestrator.py

Main pipeline tick orchestrator for Feature 22: Weekly scheduler / pipeline orchestrator.
Coordinates:
1. Distributed lock acquisition (prevents concurrent scheduler runs across replicas)
2. Discovery of finished course weeks past grace cutoff
3. Idempotent pipeline run creation
4. Sequential advancement of pending/running pipeline runs
5. Graceful lock release and structured run reporting
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db import collections as col
from app.pipeline.advance import advance_pipeline_run
from app.pipeline.clock import get_clock
from app.pipeline.discovery import create_pipeline_run, find_due_weeks
from app.pipeline.lock import acquire_lock, release_lock

logger = logging.getLogger("app.pipeline.orchestrator")


async def run_pipeline_tick(
    db: AsyncIOMotorDatabase,
    now: Optional[datetime] = None,
    dry_run: bool = False,
    include_sources: Optional[List[str]] = None,
    target_course_id: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a single iteration of the pipeline orchestrator:
    - Obtains distributed lease lock
    - Discovers due course weeks and initializes new runs
    - Progresses all pending and running runs through the stage state machine
    - Releases lock and returns summary
    """
    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if worker_id is None:
        worker_id = f"worker_{uuid.uuid4().hex[:8]}"

    lock_key = "pipeline_tick"
    lock_acquired = await acquire_lock(
        db=db,
        key=lock_key,
        owner_id=worker_id,
        lease_seconds=300,
        now=now,
    )

    if not lock_acquired:
        logger.info("Pipeline tick skipped: lease lock '%s' is held by another worker", lock_key)
        return {
            "status": "skipped",
            "reason": "lock_held",
            "executed_at": now.isoformat(),
            "runs_created": 0,
            "runs_advanced": 0,
            "created_run_ids": [],
            "advanced_run_ids": [],
        }

    try:
        # Determine course source exclusion
        if include_sources:
            allowed_set = {s.lower().strip() for s in include_sources}
            excluded_sources = [
                s for s in settings.SCHEDULER_EXCLUDED_COURSE_SOURCES
                if s.lower().strip() not in allowed_set
            ]
        else:
            excluded_sources = settings.SCHEDULER_EXCLUDED_COURSE_SOURCES

        # 1. Discover due course weeks
        due_weeks = await find_due_weeks(
            db=db,
            now=now,
            excluded_sources=excluded_sources,
            target_course_id=target_course_id,
        )

        # 2. Create pipeline runs
        created_run_ids: List[str] = []
        for cw in due_weeks:
            course_id = cw["course_id"]
            week_index = cw["week_index"]
            end_date = cw["end_date"]

            if dry_run:
                created_run_ids.append(f"dry_run_{course_id}_w{week_index}")
            else:
                doc = await create_pipeline_run(
                    db=db,
                    course_id=course_id,
                    week_index=week_index,
                    week_end=end_date,
                    trigger="scheduler",
                    triggered_by="system:scheduler",
                    now=now,
                )
                if doc:
                    created_run_ids.append(doc["run_id"])

        # 3. Advance active runs
        advance_query: Dict[str, Any] = {"status": {"$in": ["pending", "running"]}}
        if target_course_id:
            advance_query["course_id"] = target_course_id

        active_cursor = db[col.PIPELINE_RUNS].find(advance_query)
        advanced_run_ids: List[str] = []

        async for run_doc in active_cursor:
            run_id = run_doc["run_id"]
            if dry_run:
                advanced_run_ids.append(run_id)
            else:
                res = await advance_pipeline_run(db, run_doc, now=now)
                advanced_run_ids.append(res["run_id"])

        return {
            "status": "success",
            "dry_run": dry_run,
            "executed_at": now.isoformat(),
            "runs_created": len(created_run_ids),
            "runs_advanced": len(advanced_run_ids),
            "created_run_ids": created_run_ids,
            "advanced_run_ids": advanced_run_ids,
        }

    finally:
        await release_lock(db=db, key=lock_key, owner_id=worker_id)
