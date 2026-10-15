"""
backend/tests/test_feature22_scheduler.py

Test Suite for Feature 22: Weekly Telemetry Aggregation & Pipeline Trigger.
Tests activity event aggregation, academic derivation, and REST management endpoints.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import sys
from pathlib import Path

# Ensure project root, /scripts, and / are in sys.path so 'scripts' package is always resolvable
for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient

from app.core.config import settings
from app.core.database import create_mongo_client, get_db
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.jobs.weekly_aggregation import aggregate_weekly_behavior, run_weekly_pipeline
from app.main import app
from app.models.user import UserRole
from scripts.setup_db import setup_database


@pytest_asyncio.fixture
async def throwaway_pipeline_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_pipe_{uuid.uuid4().hex[:8]}"
    async_client = create_mongo_client(uri)
    db = async_client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        async_client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    # Set up indexes and collections
    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    app.dependency_overrides[get_db] = lambda: db

    # Create admin user
    admin_id = str(uuid.uuid4())
    await db[col.USERS].insert_one({
        "_id": admin_id,
        "id": admin_id,
        "email": "admin_pipe@test.edu",
        "hashed_password": hash_password("AdminPass123!"),
        "full_name": "Pipeline Admin",
        "role": UserRole.ADMIN,
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN)

    sync_client = MongoClient(uri, tz_aware=True)
    sync_db = sync_client[test_db_name]

    yield db, admin_token

    app.dependency_overrides.pop(get_db, None)
    sync_client.close()
    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


@pytest.mark.asyncio
async def test_weekly_behavior_aggregation(throwaway_pipeline_db):
    db, _ = throwaway_pipeline_db

    course_id = "CS201"
    pid = "STU_9f8e7d6c"
    now = datetime.now(timezone.utc)

    # 1. Enrol student
    await db[col.ENROLMENTS].insert_one({
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "pid": pid,
        "course_id": course_id,
        "status": "active",
        "enrolment_start": now,
        "ingested_at": now,
        "source_version": "1.0",
    })

    # 2. Insert mock activity events
    await db[col.ACTIVITY_EVENTS].insert_many([
        {
            "_id": str(uuid.uuid4()),
            "schema_version": 1,
            "pid": pid,
            "course_id": course_id,
            "week_index": 1,
            "event_type": "user_login",
            "timestamp": now,
            "clicks": 1,
            "session_minutes": 25.5,
            "ingested_at": now,
            "source_version": "1.0",
        },
        {
            "_id": str(uuid.uuid4()),
            "schema_version": 1,
            "pid": pid,
            "course_id": course_id,
            "week_index": 1,
            "event_type": "video_play",
            "timestamp": now,
            "clicks": 2,
            "event_payload": {"completion_pct": 80.0},
            "ingested_at": now,
            "source_version": "1.0",
        },
        {
            "_id": str(uuid.uuid4()),
            "schema_version": 1,
            "pid": pid,
            "course_id": course_id,
            "week_index": 1,
            "event_type": "video_pause",
            "timestamp": now,
            "clicks": 1,
            "ingested_at": now,
            "source_version": "1.0",
        },
    ])

    # 3. Insert mock submission
    await db[col.SUBMISSIONS].insert_one({
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "submission_id": "SUB_001",
        "assignment_id": "ASG_001",
        "pid": pid,
        "course_id": course_id,
        "submitted_at": now,
        "delay_hours": -1.5,
        "ingested_at": now,
        "source_version": "1.0",
    })

    # Execute aggregation
    records_count = await aggregate_weekly_behavior(
        db=db,
        course_id=course_id,
        week_index=1,
    )
    assert records_count == 1

    stored_behavior = await db[col.BEHAVIOR_WEEKLY].find_one({
        "pid": pid,
        "course_id": course_id,
        "week_index": 1,
    })
    assert stored_behavior is not None
    assert stored_behavior["login_count"] == 1
    assert stored_behavior["clicks"] == 4
    assert stored_behavior["video_play_count"] == 1
    assert stored_behavior["video_pause_count"] == 1
    assert stored_behavior["video_completion_pct"] == 80.0
    assert stored_behavior["submissions_count"] == 1
    assert stored_behavior["avg_submission_delay_hours"] == -1.5


@pytest.mark.asyncio
async def test_weekly_pipeline_endpoints(throwaway_pipeline_db):
    db, admin_token = throwaway_pipeline_db

    course_id = "CS301"
    week_index = 1
    now = datetime.now(timezone.utc)

    # Insert course and course_week
    await db[col.COURSES].insert_one({
        "_id": course_id,
        "course_id": course_id,
        "title": "Software Engineering Capstone",
        "schema_version": 1,
        "is_published": True,
        "created_at": now,
        "updated_at": now,
        "ingested_at": now,
        "source_version": "1.0",
    })
    await db[col.COURSE_WEEKS].insert_one({
        "_id": f"{course_id}_W{week_index}",
        "course_id": course_id,
        "week_index": week_index,
        "title": "Week 2",
        "start_date": now,
        "end_date": now,
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Unauthenticated request rejected
        res = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": course_id, "week_index": week_index},
        )
        assert res.status_code == 401

        # 2. Admin trigger succeeds
        res = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": course_id, "week_index": week_index, "force": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code in (200, 202)
        res_data = res.json()
        assert res_data["status"] == "accepted"
        assert "run" in res_data
        run_data = res_data["run"]
        assert run_data["course_id"] == course_id

        # Verify run in col.PIPELINE_RUNS
        run_record = await db[col.PIPELINE_RUNS].find_one({"course_id": course_id, "week_index": week_index})
        assert run_record is not None

        # 3. Check status endpoint
        status_res = await client.get(
            "/api/v1/pipeline/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "scheduler" in status_data
        assert "latest_run" in status_data
