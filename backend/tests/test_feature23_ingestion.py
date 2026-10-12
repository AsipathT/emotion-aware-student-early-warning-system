"""
backend/tests/test_feature23_ingestion.py

Test Suite for Feature 23: Component Output Ingestion API (C1, C2, C3, C4).
Validates authentication, PID integrity, idempotency, storage models, and audit logs.
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
from app.main import app
from app.models.user import UserRole
from scripts.setup_db import setup_database


@pytest_asyncio.fixture
async def throwaway_ingest_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_ingest_{uuid.uuid4().hex[:8]}"
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

    test_keys = {
        "c1": "test_key_c1",
        "c2": "test_key_c2",
        "c3": "test_key_c3",
        "c4": "test_key_c4",
    }
    original_keys = settings.component_api_keys
    settings.component_api_keys = json.dumps(test_keys)

    # Create admin user for testing
    admin_id = str(uuid.uuid4())
    await db[col.USERS].insert_one({
        "_id": admin_id,
        "id": admin_id,
        "email": "admin_ingest@test.edu",
        "hashed_password": hash_password("AdminPass123!"),
        "full_name": "Test Administrator",
        "role": UserRole.ADMIN,
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN)

    sync_client = MongoClient(uri, tz_aware=True)
    sync_db = sync_client[test_db_name]

    yield uri, test_db_name, db, sync_db, test_keys, admin_token

    app.dependency_overrides.pop(get_db, None)
    settings.component_api_keys = original_keys
    sync_client.close()
    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


@pytest.mark.asyncio
async def test_c1_affective_ingestion_matrix(throwaway_ingest_db):
    _, _, db, _, test_keys, _ = throwaway_ingest_db

    pid = "STU_1a2b3c4d"
    valid_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "c1",
        "request_id": str(uuid.uuid4()),
        "data": [
            {
                "pid": pid,
                "course_id": "CS101",
                "week_index": 2,
                "emotion_scores": {
                    "exam_anxiety": 0.85,
                    "conceptual_confusion": 0.10,
                    "academic_helplessness": 0.02,
                    "course_frustration": 0.02,
                    "motivation_erosion": 0.01,
                },
                "stress_label": "exam_anxiety",
                "confidence": 0.92,
                "message_count": 5,
                "top_drivers": [
                    {"token": "struggling", "weight": 0.78},
                    {"token": "deadline", "weight": 0.65},
                ],
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Reject without key
        res = await client.post("/api/v1/ingest/affective", json=valid_payload)
        assert res.status_code == 401

        # 2. Reject with wrong scope key (c2 key on c1 endpoint)
        res = await client.post(
            "/api/v1/ingest/affective",
            json=valid_payload,
            headers={"X-Component-Key": test_keys["c2"]},
        )
        assert res.status_code == 403

        # 3. Reject with invalid PID format
        bad_pid_payload = json.loads(json.dumps(valid_payload))
        bad_pid_payload["data"][0]["pid"] = "INVALID_PID_FORMAT"
        res = await client.post(
            "/api/v1/ingest/affective",
            json=bad_pid_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert res.status_code in (400, 422)

        # 4. Accept valid C1 payload
        res = await client.post(
            "/api/v1/ingest/affective",
            json=valid_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["data"]["status"] == "completed"
        assert res_data["data"]["records_processed"] == 1
        run_id = res_data["data"]["run_id"]

        # Verify record in col.AFFECTIVE_WEEKLY
        stored = await db[col.AFFECTIVE_WEEKLY].find_one({"pid": pid, "course_id": "CS101", "week_index": 2})
        assert stored is not None
        assert stored["stress_label"] == "exam_anxiety"
        assert stored["confidence"] == 0.92
        assert stored["ingestion_run_id"] == run_id

        # Verify col.INGESTION_RUNS
        run_record = await db[col.INGESTION_RUNS].find_one({"run_id": run_id})
        assert run_record is not None
        assert run_record["component"] == "c1"
        assert run_record["status"] == "completed"
        assert run_record["records_processed"] == 1

        # 5. Idempotent re-post updates without creating duplicate
        updated_payload = json.loads(json.dumps(valid_payload))
        updated_payload["data"][0]["confidence"] = 0.98
        res = await client.post(
            "/api/v1/ingest/affective",
            json=updated_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert res.status_code == 200
        total_count = await db[col.AFFECTIVE_WEEKLY].count_documents({"pid": pid, "course_id": "CS101", "week_index": 2})
        assert total_count == 1
        refreshed = await db[col.AFFECTIVE_WEEKLY].find_one({"pid": pid, "course_id": "CS101", "week_index": 2})
        assert refreshed["confidence"] == 0.98


@pytest.mark.asyncio
async def test_c2_behavior_ingestion(throwaway_ingest_db):
    _, _, db, _, test_keys, _ = throwaway_ingest_db

    pid = "STU_2b3c4d5e"
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "c2",
        "request_id": str(uuid.uuid4()),
        "data": [
            {
                "pid": pid,
                "course_id": "CS101",
                "week_index": 3,
                "trajectory_label": "declining",
                "confidence": 0.88,
                "contributing_indicators": ["reduced_logins", "low_video_completion"],
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/ingest/behavior",
            json=payload,
            headers={"X-Component-Key": test_keys["c2"]},
        )
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["data"]["records_processed"] == 1

        stored = await db[col.ENGAGEMENT_TRAJECTORIES].find_one({"pid": pid, "course_id": "CS101", "week_index": 3})
        assert stored is not None
        assert stored["trajectory_label"] == "declining"
        assert stored["confidence"] == 0.88


@pytest.mark.asyncio
async def test_c3_risk_ingestion(throwaway_ingest_db):
    _, _, db, _, test_keys, _ = throwaway_ingest_db

    pid = "STU_3c4d5e6f"
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "c3",
        "request_id": str(uuid.uuid4()),
        "data": [
            {
                "pid": pid,
                "course_id": "CS101",
                "week_index": 4,
                "risk_score": 0.79,
                "risk_tier": "high",
                "modality_contributions": {
                    "affective": 0.40,
                    "behavioral": 0.35,
                    "academic": 0.25,
                },
                "top_drivers": ["high_exam_anxiety", "declining_video_watch_time"],
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/ingest/risk",
            json=payload,
            headers={"X-Component-Key": test_keys["c3"]},
        )
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["data"]["records_processed"] == 1

        stored = await db[col.RISK_ASSESSMENTS].find_one({"pid": pid, "course_id": "CS101", "week_index": 4})
        assert stored is not None
        assert stored["risk_tier"] == "high"
        assert stored["risk_score"] == 0.79


@pytest.mark.asyncio
async def test_c4_recommendations_and_outcomes_matrix(throwaway_ingest_db):
    _, _, db, _, test_keys, admin_token = throwaway_ingest_db

    pid = "STU_4d5e6f7a"
    rec_id = f"REC_{uuid.uuid4().hex[:8]}"

    rec_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "c4",
        "request_id": str(uuid.uuid4()),
        "data": [
            {
                "recommendation_id": rec_id,
                "pid": pid,
                "week_index": 5,
                "candidates": [
                    {
                        "rank": 1,
                        "action_type": "academic_tutoring_session",
                        "priority": "high",
                        "rationale": "High conceptual confusion combined with low quiz scores.",
                    },
                    {
                        "rank": 2,
                        "action_type": "peer_study_group",
                        "priority": "medium",
                        "rationale": "Encourage social engagement in forum.",
                    },
                ],
                "status": "proposed",
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ingest C4 recommendation
        res = await client.post(
            "/api/v1/ingest/recommendations",
            json=rec_payload,
            headers={"X-Component-Key": test_keys["c4"]},
        )
        assert res.status_code == 200

        stored_rec = await db[col.RECOMMENDATIONS].find_one({"recommendation_id": rec_id})
        assert stored_rec is not None
        assert len(stored_rec["candidates"]) == 2

        # Verify operational sync into col.INTERVENTIONS
        interventions = await db[col.INTERVENTIONS].find({"recommendation_id": rec_id}).to_list(length=10)
        assert len(interventions) == 2

        # 2. Ingest Outcome feedback
        outcome_payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "c4",
            "request_id": str(uuid.uuid4()),
            "data": [
                {
                    "recommendation_id": rec_id,
                    "decision": "approved",
                    "completed": True,
                    "observed_change": "Student attended tutoring session and submitted next task.",
                    "notes_present": True,
                }
            ],
        }

        res = await client.post(
            "/api/v1/ingest/outcomes",
            json=outcome_payload,
            headers={"X-Component-Key": test_keys["c4"]},
        )
        assert res.status_code == 200

        stored_outcome = await db[col.INTERVENTION_OUTCOMES].find_one({"recommendation_id": rec_id})
        assert stored_outcome is not None
        assert stored_outcome["decision"] == "approved"
        assert stored_outcome["completed"] is True

        # Check status update in col.INTERVENTIONS
        updated_ints = await db[col.INTERVENTIONS].find({"recommendation_id": rec_id}).to_list(length=10)
        for it in updated_ints:
            assert it["status"] == "completed"

        # 3. Query ingestion runs as admin
        runs_res = await client.get(
            "/api/v1/ingest/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert runs_res.status_code == 200
        runs_data = runs_res.json()
        assert runs_data["total"] >= 2
        assert len(runs_data["runs"]) >= 2
