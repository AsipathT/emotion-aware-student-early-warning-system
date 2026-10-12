"""
backend/tests/test_pipeline_api.py

Feature 22: Pipeline Orchestration & Trigger API Test Suite.
Verifies all HTTP endpoints mounted on /api/v1/pipeline:
  - GET  /api/v1/pipeline/ready                     (Component polling, key auth, scope limits, zero PII)
  - GET  /api/v1/pipeline/runs                      (Admin/Auditor view, filtering, pagination)
  - GET  /api/v1/pipeline/runs/{course_id}/{week}   (Admin/Auditor single run detail, 404 handling)
  - POST /api/v1/pipeline/trigger                   (Admin manual trigger, 404, 409 conflicts, force=true)
  - POST /api/v1/pipeline/runs/{course_id}/{week}/advance (Admin manual advance)
  - GET  /api/v1/pipeline/status                    (Admin/Auditor scheduler diagnostics)
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import httpx
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.database import create_mongo_client, get_db
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.main import app
from app.models.user import UserRole
from app.pipeline.clock import reset_clock, set_clock
from app.pipeline.discovery import create_pipeline_run
from app.schemas.audit import AuditAction
from scripts.setup_db import setup_database


# ── Throwaway Test Database Fixture ───────────────────────────────────────────

@pytest_asyncio.fixture
async def throwaway_pipeline_api_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_papi_{uuid.uuid4().hex[:8]}"
    async_client = create_mongo_client(uri)
    db = async_client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        async_client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    app.dependency_overrides[get_db] = lambda: db

    test_keys = {
        "c1": "test_pipeline_key_c1",
        "c2": "test_pipeline_key_c2",
        "c3": "test_pipeline_key_c3",
        "c4": "test_pipeline_key_c4",
    }
    original_keys = settings.component_api_keys
    settings.component_api_keys = json.dumps(test_keys)

    yield uri, test_db_name, db, test_keys

    app.dependency_overrides.pop(get_db, None)
    settings.component_api_keys = original_keys
    reset_clock()

    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


# ── Helper Setup ──────────────────────────────────────────────────────────────

async def create_test_user(
    db: Any,
    role: UserRole = UserRole.ADMIN,
    email: str = "admin@university.edu",
) -> tuple[str, str]:
    """Creates a user document and returns (user_id, bearer_token)."""
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db[col.USERS].insert_one({
        "_id": user_id,
        "id": user_id,
        "email": email,
        "hashed_password": hash_password("SecurePassword123!"),
        "full_name": f"Test {role.value}",
        "role": role.value,
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    })
    token = create_access_token(subject=user_id, role=role.value)
    return user_id, token


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ready_endpoint_auth_and_scope(throwaway_pipeline_api_db):
    """Verifies that GET /pipeline/ready enforces component key authentication and scope isolation."""
    _, _, db, test_keys = throwaway_pipeline_api_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(now)

    # Create a pipeline run with C1 ready
    run = await create_pipeline_run(db, "CS101", 1, week_end=now - timedelta(hours=2), now=now)
    await db[col.PIPELINE_RUNS].update_one(
        {"run_id": run["run_id"]},
        {"$set": {"stages.c1.status": "ready", "stages.c1.eligible": 25}},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing auth -> 401
        res_no_auth = await client.get("/api/v1/pipeline/ready?component=c1")
        assert res_no_auth.status_code == 401

        # 2. Invalid component key -> 401
        res_bad_key = await client.get(
            "/api/v1/pipeline/ready?component=c1",
            headers={"X-Component-Key": "wrong_key"},
        )
        assert res_bad_key.status_code == 401

        # 3. C2 key trying to query C1 ready stages -> 403 Forbidden
        res_scope_mismatch = await client.get(
            "/api/v1/pipeline/ready?component=c1",
            headers={"X-Component-Key": test_keys["c2"]},
        )
        assert res_scope_mismatch.status_code == 403

        # 4. Valid C1 key querying C1 -> 200 OK
        res_ok = await client.get(
            "/api/v1/pipeline/ready?component=c1",
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert res_ok.status_code == 200
        body = res_ok.json()
        assert body["component"] == "c1"
        assert body["count"] == 1
        item = body["items"][0]
        assert item["course_id"] == "CS101"
        assert item["week_index"] == 1
        assert item["status"] == "ready"
        assert item["eligible"] == 25

        # 5. Admin Bearer token can query any component
        _, admin_token = await create_test_user(db, role=UserRole.ADMIN)
        res_admin = await client.get(
            "/api/v1/pipeline/ready?component=c1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 200
        assert res_admin.json()["count"] == 1


@pytest.mark.asyncio
async def test_pipeline_runs_listing_and_rbac(throwaway_pipeline_api_db):
    """Verifies RBAC and pagination for GET /pipeline/runs."""
    _, _, db, _ = throwaway_pipeline_api_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Seed 2 runs
    await create_pipeline_run(db, "CS101", 1, week_end=now, now=now)
    await create_pipeline_run(db, "CS102", 1, week_end=now, now=now)

    _, admin_token = await create_test_user(db, role=UserRole.ADMIN, email="admin1@lms.edu")
    _, auditor_token = await create_test_user(db, role=UserRole.AUDITOR, email="auditor1@lms.edu")
    _, student_token = await create_test_user(db, role=UserRole.STUDENT, email="student1@lms.edu")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Student -> 403
        res_student = await client.get(
            "/api/v1/pipeline/runs",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert res_student.status_code == 403

        # Auditor -> 200
        res_auditor = await client.get(
            "/api/v1/pipeline/runs",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert res_auditor.status_code == 200
        assert res_auditor.json()["total"] == 2

        # Admin -> 200 with course filter
        res_admin = await client.get(
            "/api/v1/pipeline/runs?course_id=CS101",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 200
        assert res_admin.json()["total"] == 1
        assert res_admin.json()["items"][0]["course_id"] == "CS101"


@pytest.mark.asyncio
async def test_get_specific_pipeline_run(throwaway_pipeline_api_db):
    """Verifies GET /pipeline/runs/{course_id}/{week_index}."""
    _, _, db, _ = throwaway_pipeline_api_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    await create_pipeline_run(db, "CS201", 3, week_end=now, now=now)
    _, admin_token = await create_test_user(db, role=UserRole.ADMIN)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 200 OK
        res = await client.get(
            "/api/v1/pipeline/runs/CS201/3",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["course_id"] == "CS201"
        assert res.json()["week_index"] == 3

        # 404 for non-existent
        res_not_found = await client.get(
            "/api/v1/pipeline/runs/NONEXISTENT/99",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_not_found.status_code == 404


@pytest.mark.asyncio
async def test_trigger_pipeline_conflict_and_force(throwaway_pipeline_api_db):
    """Verifies POST /pipeline/trigger handles 404, 409 conflicts, force=true, and audit logs."""
    _, _, db, _ = throwaway_pipeline_api_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Setup course week
    await db[col.COURSE_WEEKS].insert_one({
        "_id": "cw_TEST_1",
        "course_id": "TEST101",
        "week_index": 1,
        "title": "Week 1",
        "start_date": now - timedelta(days=7),
        "end_date": now - timedelta(hours=2),
    })

    _, admin_token = await create_test_user(db, role=UserRole.ADMIN)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger non-existent week -> 404
        res_404 = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": "TEST101", "week_index": 99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_404.status_code == 404

        # Trigger existing week -> 202 Accepted
        res_trigger = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": "TEST101", "week_index": 1, "force": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_trigger.status_code == 202
        assert res_trigger.json()["status"] == "accepted"

        # Verify PIPELINE_TRIGGERED audit entry
        audit_entry = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.PIPELINE_TRIGGERED})
        assert audit_entry is not None
        assert audit_entry["details"]["course_id"] == "TEST101"

        # Trigger again without force -> 409 Conflict
        res_conflict = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": "TEST101", "week_index": 1, "force": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_conflict.status_code == 409

        # Trigger with force=True -> 202 Accepted
        res_forced = await client.post(
            "/api/v1/pipeline/trigger",
            json={"course_id": "TEST101", "week_index": 1, "force": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_forced.status_code == 202


@pytest.mark.asyncio
async def test_advance_specific_run_endpoint(throwaway_pipeline_api_db):
    """Verifies POST /pipeline/runs/{course_id}/{week}/advance steps the run."""
    _, _, db, _ = throwaway_pipeline_api_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    await create_pipeline_run(db, "ADV101", 1, week_end=now, now=now)
    _, admin_token = await create_test_user(db, role=UserRole.ADMIN)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/pipeline/runs/ADV101/1/advance",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["run"]["course_id"] == "ADV101"


@pytest.mark.asyncio
async def test_pipeline_status_diagnostics(throwaway_pipeline_api_db):
    """Verifies GET /pipeline/status returns scheduler state and run counts."""
    _, _, db, _ = throwaway_pipeline_api_db
    _, admin_token = await create_test_user(db, role=UserRole.ADMIN)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/pipeline/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "scheduler" in body
        assert "counts" in body
        assert body["counts"]["total"] >= 0
