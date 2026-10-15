"""
backend/tests/test_export_api.py

Feature 21: Component Export API & Enrolment Router Cleanup Test Suite.
Real MongoDB execution only:
  - Part A: Enrolment router cleanup (col.ENROLMENTS, PIDs, course_id: str, 409 conflicts, migration script).
  - Part B: Component authentication (keys, scopes, 401/403/503, admin bearer, ACCESS_DENIED audit).
  - Part C: Consent & OULAD filters (accepted vs declined/withdrawn, oulad exemption, notice inactivation).
  - Part D: Privacy invariants (no PII, clean_text safety net drops, no raw text or internal storage keys).
  - Part E: Contract Envelope (Envelope[T], CONTRACT_VERSION="1.0", source="lms").
  - Part F: Pagination & filters (page_size <= 500, stable ordering, disjoint pages, invalid PID rejected).
  - Part G: Critical audit logging (EXPORT_GENERATED entry, write failure yields 500).
  - Part H: Academic derivation (build_academic_record unit tests).
  - Part I: Read-only verification (zero mutating HTTP routes on export router).
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import patch

import sys
from pathlib import Path

# Ensure project root, /scripts, and / are in sys.path so 'scripts' package is always resolvable
for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import httpx
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from pymongo import MongoClient

from app.core.academic_derivation import build_academic_record
from app.core.config import settings
from app.core.database import create_mongo_client, get_db
from app.core.privacy import pseudonymize
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.main import app
from app.models.user import UserRole
from app.routers.export import router as export_router
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import ComponentSource, Envelope
from app.schemas.contract.v1.c1_affective import TextMessageRecord
from app.schemas.contract.v1.c2_behavioral import BehaviorWeeklyRecord
from app.schemas.contract.v1.c3_risk import AcademicRecord
from scripts.migrate_enrollments import migrate_enrollments
from scripts.setup_db import setup_database


# ── Throwaway Test Database Fixture ───────────────────────────────────────────

@pytest_asyncio.fixture
async def throwaway_export_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_export_{uuid.uuid4().hex[:8]}"
    async_client = create_mongo_client(uri)
    db = async_client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        async_client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    # Initialize collections, indexes, and strict validators
    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    # Override FastAPI DI to use this test database
    app.dependency_overrides[get_db] = lambda: db

    # Configure test component keys
    test_keys = {"c1": "test_key_c1", "c2": "test_key_c2", "c3": "test_key_c3"}
    original_keys = settings.component_api_keys
    settings.component_api_keys = json.dumps(test_keys)

    sync_client = MongoClient(uri, tz_aware=True)
    sync_db = sync_client[test_db_name]

    yield uri, test_db_name, db, sync_db, test_keys

    # Teardown
    app.dependency_overrides.pop(get_db, None)
    settings.component_api_keys = original_keys
    sync_client.close()
    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


# ── PART A: Enrolment Cleanup Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrolment_part_a_flows(throwaway_export_db):
    uri, db_name, db, sync_db, _ = throwaway_export_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a course in col.COURSES
        course_id = "CS101"
        now = datetime.now(timezone.utc)
        course_doc = {
            "_id": course_id,
            "id": course_id,
            "course_id": course_id,
            "title": "Introduction to Computer Systems",
            "description": "Core course",
            "lecturer_id": str(uuid.uuid4()),
            "is_published": True,
            "modules": [],
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "created_at": now,
            "updated_at": now,
        }
        await db[col.COURSES].insert_one(course_doc)

        # 2. Student WITH PID
        raw_sid_1 = "IT20260001"
        pid_1 = pseudonymize(raw_sid_1)
        user_1_id = str(uuid.uuid4())
        user_1 = {
            "_id": user_1_id,
            "id": user_1_id,
            "email": "student1@lms.edu",
            "hashed_password": hash_password("Password123!"),
            "full_name": "Student One",
            "role": "student",
            "is_active": True,
            "student_id": raw_sid_1,
            "pid": pid_1,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        await db.users.insert_one(user_1)
        token_1 = create_access_token(user_1_id, role="student")

        # Enrol with pid and string course_id into canonical 'enrolments'
        resp = await client.post(
            f"/api/v1/enrollments/{course_id}",
            headers={"Authorization": f"Bearer {token_1}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["course_id"] == course_id
        assert body["student_id"] == user_1_id
        assert body["status"] == "active"
        assert "course" in body and body["course"]["title"] == "Introduction to Computer Systems"
        assert "student" in body and body["student"]["email"] == "student1@lms.edu"

        # Verify document written to col.ENROLMENTS
        saved = await db[col.ENROLMENTS].find_one({"pid": pid_1, "course_id": course_id})
        assert saved is not None
        assert saved["status"] == "active"

        # Duplicate active enrolment -> 409
        dup_resp = await client.post(
            f"/api/v1/enrollments/{course_id}",
            headers={"Authorization": f"Bearer {token_1}"},
        )
        assert dup_resp.status_code == 409
        assert "already enrolled" in dup_resp.json()["detail"].lower()

        # 3. Student WITHOUT PID -> 409
        user_2_id = str(uuid.uuid4())
        user_2 = {
            "_id": user_2_id,
            "id": user_2_id,
            "email": "student_nopid@lms.edu",
            "hashed_password": hash_password("Password123!"),
            "full_name": "Student No PID",
            "role": "student",
            "is_active": True,
            "student_id": "IT20260002",
            "pid": None,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        await db.users.insert_one(user_2)
        token_2 = create_access_token(user_2_id, role="student")

        no_pid_resp = await client.post(
            f"/api/v1/enrollments/{course_id}",
            headers={"Authorization": f"Bearer {token_2}"},
        )
        assert no_pid_resp.status_code == 409
        assert "pid" in no_pid_resp.json()["detail"].lower()

        # 4. GET /api/v1/enrollments/me
        me_resp = await client.get("/api/v1/enrollments/me", headers={"Authorization": f"Bearer {token_1}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert len(me_data) == 1
        assert me_data[0]["course_id"] == course_id

        # 5. Course roster maps PID -> user in single query
        admin_id = str(uuid.uuid4())
        admin_user = {
            "_id": admin_id,
            "id": admin_id,
            "email": "admin@lms.edu",
            "hashed_password": hash_password("AdminPass123!"),
            "full_name": "Admin User",
            "role": "admin",
            "is_active": True,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        await db.users.insert_one(admin_user)
        admin_token = create_access_token(admin_id, role="admin")

        roster_resp = await client.get(
            f"/api/v1/courses/{course_id}/enrollments",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert roster_resp.status_code == 200
        roster = roster_resp.json()
        assert len(roster) == 1
        assert roster[0]["student"]["email"] == "student1@lms.edu"

    # 6. Test migrate_enrollments script
    # Plant a legacy document in 'enrollments'
    legacy_user_id = str(uuid.uuid4())
    legacy_pid = pseudonymize("IT20260099")
    await db.users.insert_one({
        "_id": legacy_user_id,
        "id": legacy_user_id,
        "email": "legacy@lms.edu",
        "hashed_password": hash_password("Pass123!"),
        "full_name": "Legacy Student",
        "role": "student",
        "student_id": "IT20260099",
        "pid": legacy_pid,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })
    sync_db["enrollments"].insert_one({
        "_id": "legacy_enr_1",
        "student_id": legacy_user_id,
        "course_id": "SE4020",
        "enrolled_at": now,
        "status": "active",
    })
    # Also plant an invalid legacy row whose user has no PID
    sync_db["enrollments"].insert_one({
        "_id": "legacy_enr_nopid",
        "student_id": user_2_id,
        "course_id": "SE4020",
        "enrolled_at": now,
        "status": "active",
    })

    # Dry run test
    dry_stats = migrate_enrollments(mongo_uri=uri, db_name=db_name, dry_run=True)
    assert dry_stats["dry_run"] is True
    assert dry_stats["copied"] == 1
    assert dry_stats["skipped_no_pid"] == 1
    assert sync_db[col.ENROLMENTS].count_documents({"pid": legacy_pid}) == 0

    # Live migration test
    live_stats = migrate_enrollments(mongo_uri=uri, db_name=db_name, dry_run=False)
    assert live_stats["copied"] == 1
    assert live_stats["skipped_no_pid"] == 1
    assert sync_db[col.ENROLMENTS].count_documents({"pid": legacy_pid}) == 1
    # Verify legacy collection not dropped
    assert sync_db["enrollments"].count_documents({}) == 2

    # Second migration run (idempotency check)
    idemp_stats = migrate_enrollments(mongo_uri=uri, db_name=db_name, dry_run=False)
    assert idemp_stats["copied"] == 0
    assert idemp_stats["already_existing"] == 1


# ── PART B: Component Authentication Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_component_auth_matrix(throwaway_export_db):
    uri, db_name, db, _, keys = throwaway_export_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. No key -> 401 & ACCESS_DENIED audit log
        r_no_key = await client.get("/api/v1/export/behavior")
        assert r_no_key.status_code == 401
        audit_denied = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.ACCESS_DENIED.value})
        assert audit_denied is not None
        assert audit_denied["outcome"] == "denied"

        # 2. Wrong key -> 401
        r_wrong_key = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": "invalid_secret_key"})
        assert r_wrong_key.status_code == 401

        # 3. Scope mismatch: c1 key on /behavior -> 403
        r_scope_mismatch = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c1"]})
        assert r_scope_mismatch.status_code == 403
        assert "not authorized" in r_scope_mismatch.json()["detail"].lower()

        # 4. Valid scope: c2 key on /behavior -> 200
        r_valid_scope = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
        assert r_valid_scope.status_code == 200

        # 5. Admin bearer allowed
        admin_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        await db.users.insert_one({
            "_id": admin_id,
            "id": admin_id,
            "email": "admin_export@lms.edu",
            "hashed_password": hash_password("AdminPass123!"),
            "full_name": "Admin Tester",
            "role": "admin",
            "is_active": True,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })
        admin_token = create_access_token(admin_id, role="admin")
        r_admin = await client.get(
            "/api/v1/export/behavior",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_admin.status_code == 200

        # 6. Unconfigured keys -> 503
        with patch.object(settings, "component_api_keys", ""):
            r_unconfigured = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
            assert r_unconfigured.status_code == 503
            assert "not configured" in r_unconfigured.json()["detail"].lower()


# ── PART C & D: Consent, Privacy, & OULAD Exemption Tests ──────────────────────

@pytest.mark.asyncio
async def test_consent_and_privacy_rules(throwaway_export_db):
    uri, db_name, db, _, keys = throwaway_export_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        now = datetime.now(timezone.utc)

        # 1. Setup active consent notice v1
        await db[col.CONSENT_NOTICES].insert_one({
            "_id": "notice_v1",
            "version": 1,
            "text": "Notice v1 text for research consent testing.",
            "effective_from": now,
            "is_active": True,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })

        # Student A: Accepted
        pid_a = pseudonymize("IT20261001")
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "c_a",
            "pid": pid_a,
            "notice_version": 1,
            "decision": "accepted",
            "timestamp": now,
        })

        # Student B: Declined
        pid_b = pseudonymize("IT20261002")
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "c_b",
            "pid": pid_b,
            "notice_version": 1,
            "decision": "declined",
            "timestamp": now,
        })

        # Student C: Withdrawn (accepted earlier, withdrawn later)
        pid_c = pseudonymize("IT20261003")
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "c_c_1",
            "pid": pid_c,
            "notice_version": 1,
            "decision": "accepted",
            "timestamp": now - timedelta(hours=2),
        })
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "c_c_2",
            "pid": pid_c,
            "notice_version": 1,
            "decision": "withdrawn",
            "timestamp": now,
        })

        # Student D: No consent record
        pid_d = pseudonymize("IT20261004")

        # Student O: OULAD student (no consent, research exempt)
        pid_o = pseudonymize("IT20261099")

        # Seed behavior records
        for p in [pid_a, pid_b, pid_c, pid_d]:
            await db[col.BEHAVIOR_WEEKLY].insert_one({
                "_id": f"beh_{p}",
                "pid": p,
                "course_id": "CS101",
                "week_index": 0,
                "login_count": 4,
                "session_minutes": 100.0,
                "clicks": 30,
                "video_play_count": 2,
                "video_pause_count": 1,
                "video_rewind_count": 0,
                "video_skip_count": 0,
                "video_completion_pct": 75.0,
                "submissions_count": 1,
                "avg_submission_delay_hours": -1.0,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
                "source": "synthetic",
            })

        # Insert OULAD exempt record
        await db[col.BEHAVIOR_WEEKLY].insert_one({
            "_id": f"beh_{pid_o}",
            "pid": pid_o,
            "course_id": "CS101",
            "week_index": 0,
            "login_count": 7,
            "session_minutes": 140.0,
            "clicks": 45,
            "video_play_count": 0,
            "video_pause_count": 0,
            "video_rewind_count": 0,
            "video_skip_count": 0,
            "video_completion_pct": 0.0,
            "submissions_count": 1,
            "avg_submission_delay_hours": 0.0,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "oulad",
        })

        # Query /behavior with C2 key
        resp = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
        assert resp.status_code == 200
        res_pids = {item["pid"] for item in resp.json()["data"]}

        # Accepted student (A) and OULAD student (O) must be included
        assert pid_a in res_pids
        assert pid_o in res_pids
        # Declined (B), Withdrawn (C), and No-Record (D) must be excluded
        assert pid_b not in res_pids
        assert pid_c not in res_pids
        assert pid_d not in res_pids

        # Privacy safety net test on /messages
        # Message 1: Clean
        await db[col.MESSAGES].insert_one({
            "_id": "msg_clean",
            "message_id": "msg_clean",
            "pid": pid_a,
            "course_id": "CS101",
            "week_index": 0,
            "source_type": "forum",
            "clean_text": "A clean discussion comment without identifying data.",
            "timestamp": now,
            "message_length_chars": 51,
            "message_length_words": 7,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "synthetic",
        })
        # Message 2: Leaks an email in clean_text
        await db[col.MESSAGES].insert_one({
            "_id": "msg_leak",
            "message_id": "msg_leak",
            "pid": pid_a,
            "course_id": "CS101",
            "week_index": 0,
            "source_type": "forum",
            "clean_text": "Please contact student@lms.edu for the notes.",
            "timestamp": now,
            "message_length_chars": 45,
            "message_length_words": 7,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "synthetic",
        })

        m_resp = await client.get("/api/v1/export/messages", headers={"X-Component-Key": keys["c1"]})
        assert m_resp.status_code == 200
        m_body = m_resp.json()
        assert len(m_body["data"]) == 1
        assert m_body["data"][0]["message_id"] == "msg_clean"

        # Verify audit log recorded skipped_count = 1
        m_audit = await db[col.AUDIT_LOGS].find_one({"target_id": "messages"}, sort=[("timestamp", -1)])
        assert m_audit is not None
        assert m_audit["details"]["skipped_count"] == 1
        assert m_audit["details"]["row_count"] == 1

        # Privacy verification: Entire response contains zero PII or internal keys
        raw_response_text = json.dumps(m_body)
        assert "student@lms.edu" not in raw_response_text
        assert "_id" not in m_body["data"][0]
        assert "source" not in m_body["data"][0]
        assert "raw_text" not in raw_response_text

        # Student A later withdraws: must disappear from subsequent export
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "c_a_withdrawn",
            "pid": pid_a,
            "notice_version": 1,
            "decision": "withdrawn",
            "timestamp": now + timedelta(hours=1),
        })
        resp_after_withdraw = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
        assert resp_after_withdraw.status_code == 200
        res_pids_after = {item["pid"] for item in resp_after_withdraw.json()["data"]}
        assert pid_a not in res_pids_after
        assert pid_o in res_pids_after

        # No active notice: only OULAD records returned
        await db[col.CONSENT_NOTICES].update_many({}, {"$set": {"is_active": False}})
        resp_no_notice = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
        assert resp_no_notice.status_code == 200
        pids_no_notice = {item["pid"] for item in resp_no_notice.json()["data"]}
        assert pids_no_notice == {pid_o}
    finally:
        await client.aclose()


# ── PART E & F: Contract, Pagination, and Filters ─────────────────────────────

@pytest.mark.asyncio
async def test_contract_pagination_and_filters(throwaway_export_db):
    uri, db_name, db, _, keys = throwaway_export_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        now = datetime.now(timezone.utc)

        # Active consent notice
        await db[col.CONSENT_NOTICES].insert_one({
            "_id": "notice_v1",
            "version": 1,
            "text": "Active notice",
            "effective_from": now,
            "is_active": True,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })

        # Seed 10 records for student with consent
        pid = pseudonymize("IT20265555")
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": "consent_5555",
            "pid": pid,
            "notice_version": 1,
            "decision": "accepted",
            "timestamp": now,
        })

        for w in range(10):
            await db[col.BEHAVIOR_WEEKLY].insert_one({
                "_id": f"beh_5555_{w}",
                "pid": pid,
                "course_id": "CS101",
                "week_index": w,
                "login_count": 3,
                "session_minutes": 60.0,
                "clicks": 20,
                "video_play_count": 1,
                "video_pause_count": 1,
                "video_rewind_count": 0,
                "video_skip_count": 0,
                "video_completion_pct": 100.0,
                "submissions_count": 1,
                "avg_submission_delay_hours": 0.0,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
                "source": "synthetic",
            })

        # Page size > 500 rejected with 422
        r_bad_size = await client.get("/api/v1/export/behavior?page_size=501", headers={"X-Component-Key": keys["c2"]})
        assert r_bad_size.status_code == 422

        # Disjoint pagination (page 1 and page 2 with page_size=4)
        r_p1 = await client.get("/api/v1/export/behavior?page=1&page_size=4", headers={"X-Component-Key": keys["c2"]})
        assert r_p1.status_code == 200
        p1_data = r_p1.json()
        assert p1_data["total"] == 10
        assert len(p1_data["data"]) == 4

        r_p2 = await client.get("/api/v1/export/behavior?page=2&page_size=4", headers={"X-Component-Key": keys["c2"]})
        assert r_p2.status_code == 200
        p2_data = r_p2.json()
        assert len(p2_data["data"]) == 4

        p1_weeks = [item["week_index"] for item in p1_data["data"]]
        p2_weeks = [item["week_index"] for item in p2_data["data"]]
        # Ensure stable ordering and disjoint sets
        assert p1_weeks == [0, 1, 2, 3]
        assert p2_weeks == [4, 5, 6, 7]
        assert set(p1_weeks).isdisjoint(set(p2_weeks))

        # Envelope validation
        env = Envelope[List[BehaviorWeeklyRecord]].model_validate(p1_data)
        assert env.schema_version == "1.0"
        assert env.source == ComponentSource.LMS

        # Filtering by week range
        r_week = await client.get("/api/v1/export/behavior?week_from=3&week_to=5", headers={"X-Component-Key": keys["c2"]})
        assert r_week.status_code == 200
        week_res = [item["week_index"] for item in r_week.json()["data"]]
        assert week_res == [3, 4, 5]

        # Invalid PID rejected with 400
        r_bad_pid = await client.get("/api/v1/export/behavior?pid=NOT_A_PID", headers={"X-Component-Key": keys["c2"]})
        assert r_bad_pid.status_code == 400
    finally:
        await client.aclose()


# ── PART G: Critical Audit Log Verification ───────────────────────────────────

@pytest.mark.asyncio
async def test_audit_export_generated_and_forced_failure(throwaway_export_db):
    uri, db_name, db, _, keys = throwaway_export_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        # Normal export writes EXPORT_GENERATED audit log
        r_ok = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
        assert r_ok.status_code == 200

        audit_entry = await db[col.AUDIT_LOGS].find_one(
            {"action": AuditAction.EXPORT_GENERATED.value, "target_id": "behavior"},
            sort=[("timestamp", -1)],
        )
        assert audit_entry is not None
        assert audit_entry["actor_id"] == "component:c2"
        assert "filters" in audit_entry["details"]
        assert "row_count" in audit_entry["details"]
        # Ensure no data payload in details
        assert "data" not in audit_entry["details"]

        # Forced audit failure blocks export with HTTP 500
        with patch("app.services.audit.insert_audit_log", side_effect=RuntimeError("Database write failure")):
            r_fail = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": keys["c2"]})
            assert r_fail.status_code == 500
            assert "audit logging failed" in r_fail.json()["detail"].lower()
    finally:
        await client.aclose()


# ── PART H: Academic Derivation Unit Tests ────────────────────────────────────

def test_build_academic_record_unit():
    pid = "STU_a1b2c3d4"
    course_id = "CS101"
    week_index = 2

    # Case 1: Continuous assessment with weights, null midterm, no quizzes, no submissions
    grades = [
        {"grade_item": "TMA 1", "score": 80.0, "max_score": 100.0, "weight_pct": 20.0},
        {"grade_item": "TMA 2", "score": 90.0, "max_score": 100.0, "weight_pct": 30.0},
    ]
    # Attendance with zero scheduled sessions
    attendance = {
        "sessions_scheduled": 0,
        "sessions_attended": 0,
        "attendance_pct": 100.0,
    }

    record = build_academic_record(
        pid=pid,
        course_id=course_id,
        week_index=week_index,
        grades=grades,
        attendance=attendance,
        submissions=[],
        quiz_attempts=[],
    )

    # Weighted mean: (80*20 + 90*30) / (20 + 30) = (1600 + 2700) / 50 = 4300 / 50 = 86.0
    assert record.ca_marks == 86.0
    assert record.midterm_mark is None
    assert record.quiz_scores == []
    assert record.attendance_pct == 100.0
    assert record.submission_delay_hours == 0.0

    # Case 2: Midterm item present, quiz attempts present, submissions present
    grades_midterm = [
        {"grade_item": "MIDTERM EXAM", "score": 75.0, "max_score": 100.0},
    ]
    quiz_attempts = [
        {"quiz_id": "Q1", "score": 18.0},
    ]
    quizzes_map = {"Q1": {"max_score": 20.0}}
    submissions = [
        {"delay_hours": -4.0},
        {"delay_hours": -2.0},
    ]
    att_normal = {
        "sessions_scheduled": 4,
        "sessions_attended": 3,
    }

    record_2 = build_academic_record(
        pid=pid,
        course_id=course_id,
        week_index=week_index,
        grades=grades_midterm,
        attendance=att_normal,
        submissions=submissions,
        quiz_attempts=quiz_attempts,
        quizzes_map=quizzes_map,
    )

    assert record_2.ca_marks is None
    assert record_2.midterm_mark == 75.0
    assert record_2.quiz_scores == [90.0]
    assert record_2.attendance_pct == 75.0
    assert record_2.submission_delay_hours == -3.0


# ── PART I: Read-Only Router Verification ─────────────────────────────────────

def test_export_router_is_strictly_read_only():
    """Verifies that no non-GET endpoints exist on the export router."""
    for route in export_router.routes:
        methods = getattr(route, "methods", set())
        assert methods == {"GET"} or methods == {"GET", "HEAD"}, (
            f"Route '{route.path}' defines non-read-only HTTP methods: {methods}"
        )
