"""
backend/tests/test_export_readback.py

Integration and Regression Test Suite for Component Read-Back Endpoints:
  - GET /api/v1/export/affective   (C3, C4)
  - GET /api/v1/export/trajectory  (C3, C4)
  - GET /api/v1/export/risk        (C4)
  - GET /api/v1/export/outcomes    (C4)

Tests against isolated REAL MongoDB Atlas test databases (MONGODB_TEST_URI).
Verifies:
  1. Startup key validation (dev warning vs prod refusal)
  2. Component auth matrix (scopes, admin bearer, failed audit)
  3. Consent gating, OULAD exemption, and withdrawal revocation
  4. Privacy & PII safety nets (no identifying fields, no leaks)
  5. Feature 24 contract conformance across all 7 export endpoints
  6. Filters, pagination, and stable sorting
  7. Critical audit logging (EXPORT_GENERATED before return, forced failure = 500)
  8. End-to-end ingestion -> read-back round-trip fidelity
  9. Strict read-only invariant (GET only)
"""

import copy
import json
import os
import sys
from pathlib import Path
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import patch

# Ensure project root & scripts directory are in sys.path
for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from app.core.config import settings
from app.core.component_auth import validate_component_api_keys
from app.core.database import create_mongo_client, get_db
from app.core.privacy import is_valid_pid, pseudonymize
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.main import app
from app.schemas.audit import AuditAction
from app.schemas.contract.common import (
    ComponentSource,
    Decision,
    DistressClass,
    Envelope,
    RiskTier,
    TrajectoryLabel,
)
from app.schemas.contract.v1.c1_affective import AffectiveWeeklyVector, TextMessageRecord
from app.schemas.contract.v1.c2_behavioral import BehaviorWeeklyRecord, EngagementTrajectory
from app.schemas.contract.v1.c3_risk import AcademicRecord, RiskAssessment
from app.schemas.contract.v1.c4_intervention import InterventionOutcome
from scripts.setup_db import setup_database


VALID_EMOTION_SCORES = {
    "exam_anxiety": 0.20,
    "conceptual_confusion": 0.20,
    "academic_helplessness": 0.20,
    "course_frustration": 0.20,
    "motivation_erosion": 0.20,
}


# ── TEST FIXTURES ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def throwaway_readback_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_readback_{uuid.uuid4().hex[:8]}"
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

    test_keys = {
        "c1": "c1_test_secret_key_long_enough_24chars",
        "c2": "c2_test_secret_key_long_enough_24chars",
        "c3": "c3_test_secret_key_long_enough_24chars",
        "c4": "c4_test_secret_key_long_enough_24chars",
    }

    orig_keys_raw = settings.component_api_keys
    settings.component_api_keys = json.dumps(test_keys)

    sync_client = MongoClient(uri, tz_aware=True)
    sync_db = sync_client[test_db_name]

    yield db, test_keys, sync_db, test_db_name

    # Teardown
    app.dependency_overrides.pop(get_db, None)
    settings.component_api_keys = orig_keys_raw
    sync_client.close()
    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


# ── HELPER DATA SETUP ─────────────────────────────────────────────────────────

async def setup_student_and_course(
    db,
    pid: str,
    course_id: str = "CS101",
    consent_decision: str = "accepted",
    is_oulad: bool = False,
    notice_version: int = 1,
):
    now = datetime.now(timezone.utc)

    # 1. Identity Vault
    await db[col.IDENTITY_VAULT].update_one(
        {"pid": pid},
        {
            "$set": {
                "_id": pid,
                "pid": pid,
                "student_id": f"SID_{pid[-8:]}",
                "name": f"Student {pid[-4:]}",
                "email": f"stu_{pid[-4:]}@example.edu",
                "is_imported": is_oulad,
                "source": "oulad" if is_oulad else "synthetic",
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
        upsert=True,
    )

    # 2. Consent Notice & Record
    await db[col.CONSENT_NOTICES].update_one(
        {"version": notice_version},
        {
            "$set": {
                "_id": f"notice_v{notice_version}",
                "version": notice_version,
                "text": "Mandatory ethical data processing notice for research analytics.",
                "effective_from": now,
                "is_active": True,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
        upsert=True,
    )

    if consent_decision:
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": f"c_{pid}_{uuid.uuid4().hex[:6]}",
            "pid": pid,
            "notice_version": notice_version,
            "decision": consent_decision,
            "timestamp": now,
            "ip_or_client": "127.0.0.1",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })

    # 3. Course & Enrolment
    await db[col.COURSES].update_one(
        {"course_id": course_id},
        {
            "$set": {
                "_id": course_id,
                "course_id": course_id,
                "title": f"Course {course_id}",
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
        upsert=True,
    )

    await db[col.ENROLMENTS].update_one(
        {"pid": pid, "course_id": course_id},
        {
            "$set": {
                "_id": f"enr_{pid}_{course_id}",
                "pid": pid,
                "course_id": course_id,
                "status": "active",
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
        upsert=True,
    )


# ── TEST 1: Startup Key Validation ────────────────────────────────────────────

def test_startup_key_validation():
    """Verifies startup key check: warning in dev, refusal in prod."""
    # 1. Valid keys in prod -> passes
    valid_keys = {"c1": "a" * 24, "c2": "b" * 32}
    validate_component_api_keys(valid_keys, app_env="production")

    # 2. Short key in prod -> raises RuntimeError
    short_keys = {"c1": "short_key_under_24"}
    with pytest.raises(RuntimeError, match="shorter than 24"):
        validate_component_api_keys(short_keys, app_env="production")

    # 3. Placeholder key in prod -> raises RuntimeError
    placeholder_keys = {"c1": "my_key_change_in_production_1234"}
    with pytest.raises(RuntimeError, match="change_in_production"):
        validate_component_api_keys(placeholder_keys, app_env="production")

    # 4. Short / placeholder in development -> logs warning, does not raise
    validate_component_api_keys(short_keys, app_env="development")
    validate_component_api_keys(placeholder_keys, app_env="development")

    # 5. Empty / unset keys -> logs warning, does not raise
    validate_component_api_keys({}, app_env="development")


# ── TEST 2: Read-Back Authentication Matrix ───────────────────────────────────

@pytest.mark.asyncio
async def test_readback_auth_matrix(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    pid = pseudonymize("STU_AUTH_001")
    course_id = "CS101"
    await setup_student_and_course(db, pid, course_id, consent_decision="accepted")

    now = datetime.now(timezone.utc)
    # Seed affective, trajectory, risk, outcomes
    await db[col.AFFECTIVE_WEEKLY].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "emotion_scores": VALID_EMOTION_SCORES,
        "stress_label": "conceptual_confusion",
        "confidence": 0.9,
        "message_count": 5,
        "top_drivers": [],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })
    await db[col.ENGAGEMENT_TRAJECTORIES].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "trajectory_label": "stable",
        "confidence": 0.88,
        "contributing_indicators": ["daily_logins"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })
    await db[col.RISK_ASSESSMENTS].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "risk_score": 0.25,
        "risk_tier": "low",
        "modality_contributions": {"affective": 0.33, "behavioral": 0.33, "academic": 0.34},
        "top_drivers": ["attendance_high"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })
    await db[col.RECOMMENDATIONS].insert_one({
        "_id": f"REC_{pid}_0",
        "recommendation_id": f"REC_{pid}_0",
        "pid": pid,
        "week_index": 0,
        "candidates": [{"rank": 1, "suitability_score": 0.9, "rationale": "Tutoring", "intervention_type": "peer_tutoring"}],
        "status": "proposed",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })
    await db[col.INTERVENTION_OUTCOMES].insert_one({
        "_id": f"OUT_{pid}_0",
        "recommendation_id": f"REC_{pid}_0",
        "decision": "approved",
        "completed": True,
        "observed_change": "Grade improved",
        "notes_present": False,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "staff",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. /affective: C3 and C4 -> 200; C1 -> 403; missing key -> 401
        r_aff_c3 = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c3"]})
        assert r_aff_c3.status_code == 200
        r_aff_c4 = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c4"]})
        assert r_aff_c4.status_code == 200
        r_aff_c1 = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c1"]})
        assert r_aff_c1.status_code == 403
        r_aff_nokey = await client.get("/api/v1/export/affective")
        assert r_aff_nokey.status_code == 401

        # 2. /trajectory: C3 and C4 -> 200; C2 -> 403
        r_traj_c3 = await client.get("/api/v1/export/trajectory", headers={"X-Component-Key": test_keys["c3"]})
        assert r_traj_c3.status_code == 200
        r_traj_c4 = await client.get("/api/v1/export/trajectory", headers={"X-Component-Key": test_keys["c4"]})
        assert r_traj_c4.status_code == 200
        r_traj_c2 = await client.get("/api/v1/export/trajectory", headers={"X-Component-Key": test_keys["c2"]})
        assert r_traj_c2.status_code == 403

        # 3. /risk: C4 -> 200; C3 -> 403
        r_risk_c4 = await client.get("/api/v1/export/risk", headers={"X-Component-Key": test_keys["c4"]})
        assert r_risk_c4.status_code == 200
        r_risk_c3 = await client.get("/api/v1/export/risk", headers={"X-Component-Key": test_keys["c3"]})
        assert r_risk_c3.status_code == 403

        # 4. /outcomes: C4 -> 200; C3 -> 403
        r_out_c4 = await client.get("/api/v1/export/outcomes", headers={"X-Component-Key": test_keys["c4"]})
        assert r_out_c4.status_code == 200
        r_out_c3 = await client.get("/api/v1/export/outcomes", headers={"X-Component-Key": test_keys["c3"]})
        assert r_out_c3.status_code == 403

        # 5. Admin bearer allowed on all read-only exports
        admin_id = str(uuid.uuid4())
        await db.users.insert_one({
            "_id": admin_id,
            "id": admin_id,
            "email": "admin_readback@lms.edu",
            "hashed_password": hash_password("AdminPass123!"),
            "full_name": "Admin Tester",
            "role": "admin",
            "is_active": True,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })
        admin_token = create_access_token(admin_id, role="admin")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        assert (await client.get("/api/v1/export/affective", headers=admin_headers)).status_code == 200
        assert (await client.get("/api/v1/export/trajectory", headers=admin_headers)).status_code == 200
        assert (await client.get("/api/v1/export/risk", headers=admin_headers)).status_code == 200
        assert (await client.get("/api/v1/export/outcomes", headers=admin_headers)).status_code == 200

        # 6. Unconfigured keys -> 503
        with patch.object(settings, "component_api_keys", ""):
            r_unconf = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c3"]})
            assert r_unconf.status_code == 503

        # 7. Denied attempts audited as ACCESS_DENIED
        audit_denied = await db[col.AUDIT_LOGS].find_one({
            "action": AuditAction.ACCESS_DENIED.value,
            "target_type": "export",
        })
        assert audit_denied is not None
        assert audit_denied["outcome"] == "denied"


# ── TEST 3: Consent Gating, OULAD Exemption & Withdrawal ───────────────────────

@pytest.mark.asyncio
async def test_readback_consent_and_oulad_gating(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    now = datetime.now(timezone.utc)

    pid_accepted = pseudonymize("STU_CONSENT_ACC")
    pid_declined = pseudonymize("STU_CONSENT_DEC")
    pid_withdrawn = pseudonymize("STU_CONSENT_WIT")
    pid_norecord = pseudonymize("STU_CONSENT_NONE")
    pid_oulad = pseudonymize("STU_CONSENT_OULAD")

    await setup_student_and_course(db, pid_accepted, course_id, consent_decision="accepted")
    await setup_student_and_course(db, pid_declined, course_id, consent_decision="declined")
    await setup_student_and_course(db, pid_norecord, course_id, consent_decision=None)
    await setup_student_and_course(db, pid_oulad, course_id, consent_decision=None, is_oulad=True)

    # Student Withdrawn: accepted earlier, withdrawn later
    await setup_student_and_course(db, pid_withdrawn, course_id, consent_decision="accepted")
    await db[col.CONSENT_RECORDS].insert_one({
        "_id": f"c_{pid_withdrawn}_withdrawn",
        "pid": pid_withdrawn,
        "notice_version": 1,
        "decision": "withdrawn",
        "timestamp": now + timedelta(seconds=10),
        "ip_or_client": "127.0.0.1",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })

    # Seed data across all students
    all_pids = [pid_accepted, pid_declined, pid_withdrawn, pid_norecord, pid_oulad]
    for p in all_pids:
        # Affective record
        await db[col.AFFECTIVE_WEEKLY].insert_one({
            "_id": f"{p}__{course_id}__0",
            "pid": p,
            "course_id": course_id,
            "week_index": 0,
            "emotion_scores": VALID_EMOTION_SCORES,
            "stress_label": "conceptual_confusion",
            "confidence": 0.9,
            "message_count": 3,
            "top_drivers": [],
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "oulad" if p == pid_oulad else "ingest",
        })

        # Trajectory record
        await db[col.ENGAGEMENT_TRAJECTORIES].insert_one({
            "_id": f"{p}__{course_id}__0",
            "pid": p,
            "course_id": course_id,
            "week_index": 0,
            "trajectory_label": "stable",
            "confidence": 0.85,
            "contributing_indicators": ["portal_activity"],
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "oulad" if p == pid_oulad else "ingest",
        })

        # Risk record
        await db[col.RISK_ASSESSMENTS].insert_one({
            "_id": f"{p}__{course_id}__0",
            "pid": p,
            "course_id": course_id,
            "week_index": 0,
            "risk_score": 0.30,
            "risk_tier": "low",
            "modality_contributions": {"affective": 0.33, "behavioral": 0.33, "academic": 0.34},
            "top_drivers": ["attendance_good"],
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "oulad" if p == pid_oulad else "ingest",
        })

        # Recommendation and Outcome
        rec_id = f"REC_{p}_0"
        await db[col.RECOMMENDATIONS].insert_one({
            "_id": rec_id,
            "recommendation_id": rec_id,
            "pid": p,
            "week_index": 0,
            "candidates": [{"rank": 1, "suitability_score": 0.9, "rationale": "Advising", "intervention_type": "academic_advising"}],
            "status": "proposed",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "oulad" if p == pid_oulad else "ingest",
        })
        await db[col.INTERVENTION_OUTCOMES].insert_one({
            "_id": f"OUT_{p}_0",
            "recommendation_id": rec_id,
            "decision": "approved",
            "completed": True,
            "observed_change": "Satisfactory progress",
            "notes_present": False,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "source": "staff",
        })

    # Add one orphan outcome whose recommendation does not exist
    await db[col.INTERVENTION_OUTCOMES].insert_one({
        "_id": "OUT_ORPHAN_999",
        "recommendation_id": "REC_DOES_NOT_EXIST",
        "decision": "rejected",
        "completed": False,
        "observed_change": None,
        "notes_present": False,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "staff",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check /affective
        r_aff = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c4"]})
        assert r_aff.status_code == 200
        pids_aff = {item["pid"] for item in r_aff.json()["data"]}
        assert pid_accepted in pids_aff
        assert pid_oulad in pids_aff
        assert pid_declined not in pids_aff
        assert pid_withdrawn not in pids_aff
        assert pid_norecord not in pids_aff

        # Check /trajectory
        r_traj = await client.get("/api/v1/export/trajectory", headers={"X-Component-Key": test_keys["c4"]})
        assert r_traj.status_code == 200
        pids_traj = {item["pid"] for item in r_traj.json()["data"]}
        assert pids_traj == {pid_accepted, pid_oulad}

        # Check /risk
        r_risk = await client.get("/api/v1/export/risk", headers={"X-Component-Key": test_keys["c4"]})
        assert r_risk.status_code == 200
        pids_risk = {item["pid"] for item in r_risk.json()["data"]}
        assert pids_risk == {pid_accepted, pid_oulad}

        # Check /outcomes: filters through recommendation's PID
        r_out = await client.get("/api/v1/export/outcomes", headers={"X-Component-Key": test_keys["c4"]})
        assert r_out.status_code == 200
        out_data = r_out.json()["data"]
        rec_ids_out = {item["recommendation_id"] for item in out_data}
        assert f"REC_{pid_accepted}_0" in rec_ids_out
        assert f"REC_{pid_oulad}_0" in rec_ids_out
        assert f"REC_{pid_declined}_0" not in rec_ids_out
        assert f"REC_{pid_withdrawn}_0" not in rec_ids_out
        assert "REC_DOES_NOT_EXIST" not in rec_ids_out

        # Verify orphan and non-consenting outcomes were counted as skipped
        audit_out = await db[col.AUDIT_LOGS].find_one(
            {"action": AuditAction.EXPORT_GENERATED.value, "target_id": "outcomes"},
            sort=[("timestamp", -1)],
        )
        assert audit_out is not None
        assert audit_out["details"]["row_count"] == 2
        assert audit_out["details"]["skipped_count"] >= 3  # declined, withdrawn, orphan

        # 4. Student accepted later withdraws -> disappears from next read
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": f"c_{pid_accepted}_withdrawn_later",
            "pid": pid_accepted,
            "notice_version": 1,
            "decision": "withdrawn",
            "timestamp": datetime.now(timezone.utc),
            "ip_or_client": "127.0.0.1",
            "schema_version": 1,
            "ingested_at": datetime.now(timezone.utc),
            "source_version": "1.0",
        })
        r_aff_after = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c4"]})
        pids_after = {item["pid"] for item in r_aff_after.json()["data"]}
        assert pid_accepted not in pids_after
        assert pid_oulad in pids_after

        # 5. With no active notice -> ONLY OULAD identities pass
        await db[col.CONSENT_NOTICES].update_many({}, {"$set": {"is_active": False}})
        r_aff_nonotice = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c4"]})
        pids_nonotice = {item["pid"] for item in r_aff_nonotice.json()["data"]}
        assert pids_nonotice == {pid_oulad}


# ── TEST 4: Privacy & PII Safety Nets ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_readback_privacy_and_pii_safety(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    now = datetime.now(timezone.utc)
    pid_clean = pseudonymize("STU_PII_CLEAN")
    pid_dirty = pseudonymize("STU_PII_DIRTY")

    await setup_student_and_course(db, pid_clean, course_id, consent_decision="accepted")
    await setup_student_and_course(db, pid_dirty, course_id, consent_decision="accepted")

    # Clean records
    await db[col.AFFECTIVE_WEEKLY].insert_one({
        "_id": f"{pid_clean}__{course_id}__0",
        "pid": pid_clean,
        "course_id": course_id,
        "week_index": 0,
        "emotion_scores": VALID_EMOTION_SCORES,
        "stress_label": "conceptual_confusion",
        "confidence": 0.95,
        "message_count": 2,
        "top_drivers": [{"token_or_marker": "homework", "weight": 0.4}],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    # Dirty record with email in top_driver token
    await db[col.AFFECTIVE_WEEKLY].insert_one({
        "_id": f"{pid_dirty}__{course_id}__0",
        "pid": pid_dirty,
        "course_id": course_id,
        "week_index": 0,
        "emotion_scores": VALID_EMOTION_SCORES,
        "stress_label": "leaked_student@university.edu",
        "confidence": 0.95,
        "message_count": 2,
        "top_drivers": [],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c4"]})
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Only clean record is returned; dirty record dropped
        assert len(data) == 1
        rec = data[0]
        assert rec["pid"] == pid_clean

        # Raw representation checks: no forbidden storage fields
        assert "_id" not in rec
        assert "student_id" not in rec
        assert "source_version" not in rec
        assert "ingestion_run_id" not in rec

        raw_str = json.dumps(resp.json())
        assert '"_id":' not in raw_str
        assert "student_id" not in raw_str
        assert "source_version" not in raw_str
        assert "ingestion_run_id" not in raw_str
        assert "leaked_student@university.edu" not in raw_str


# ── TEST 5: Feature 24 Contract Conformance Across All 7 Export Routes ─────────

@pytest.mark.asyncio
async def test_contract_conformance_all_endpoints(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    now = datetime.now(timezone.utc)
    pid = pseudonymize("STU_CONTRACT_PASS")
    await setup_student_and_course(db, pid, course_id, consent_decision="accepted")

    # 1. Messages (LMS -> C1)
    await db[col.MESSAGES].insert_one({
        "_id": "msg_conf_1",
        "message_id": "MSG_CONF_1",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "source_type": "forum",
        "clean_text": "Good lecture on data structures.",
        "timestamp": now,
        "message_length_chars": 32,
        "message_length_words": 5,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "seed",
    })

    # 2. Behavior (LMS -> C2)
    await db[col.BEHAVIOR_WEEKLY].insert_one({
        "_id": f"beh_{pid}_{course_id}_0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "login_count": 5,
        "session_minutes": 120.0,
        "clicks": 45,
        "video_play_count": 3,
        "video_pause_count": 2,
        "video_rewind_count": 1,
        "video_skip_count": 0,
        "video_completion_pct": 85.5,
        "submissions_count": 2,
        "avg_submission_delay_hours": -2.5,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "seed",
    })

    # 3. Academic (LMS -> C3 derived via grades & attendance)
    await db[col.GRADES].insert_one({
        "_id": f"grd_{pid}_{course_id}_0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "grade_item": "TMA 01",
        "score": 85.0,
        "max_score": 100.0,
        "weight_pct": 20.0,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "seed",
    })
    await db[col.ATTENDANCE].insert_one({
        "_id": f"att_{pid}_{course_id}_0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "sessions_scheduled": 2,
        "sessions_attended": 2,
        "attendance_pct": 100.0,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "seed",
    })

    # 4. Affective (C1 -> LMS)
    await db[col.AFFECTIVE_WEEKLY].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "emotion_scores": VALID_EMOTION_SCORES,
        "stress_label": "conceptual_confusion",
        "confidence": 0.92,
        "message_count": 4,
        "top_drivers": [{"token_or_marker": "clarity", "weight": 0.5}],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    # 5. Trajectory (C2 -> LMS)
    await db[col.ENGAGEMENT_TRAJECTORIES].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "trajectory_label": "improving",
        "confidence": 0.89,
        "contributing_indicators": ["increased_video_plays"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    # 6. Risk (C3 -> LMS)
    await db[col.RISK_ASSESSMENTS].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "risk_score": 0.18,
        "risk_tier": "low",
        "modality_contributions": {"affective": 0.20, "behavioral": 0.30, "academic": 0.50},
        "top_drivers": ["high_continuous_assessment"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    # 7. Recommendations & Outcomes (C4 -> LMS feedback)
    rec_id = f"REC_{pid}_0"
    await db[col.RECOMMENDATIONS].insert_one({
        "_id": rec_id,
        "recommendation_id": rec_id,
        "pid": pid,
        "week_index": 0,
        "candidates": [
            {"rank": 1, "suitability_score": 0.95, "rationale": "Enrichment tasks", "intervention_type": "advanced_reading"},
        ],
        "status": "proposed",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })
    await db[col.INTERVENTION_OUTCOMES].insert_one({
        "_id": f"OUT_{pid}_0",
        "recommendation_id": rec_id,
        "decision": "approved",
        "completed": True,
        "observed_change": "Student completed advanced reading modules",
        "notes_present": False,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "staff",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. /messages
        r_msg = await client.get("/api/v1/export/messages", headers={"X-Component-Key": test_keys["c1"]})
        assert r_msg.status_code == 200
        env_msg = Envelope[List[TextMessageRecord]].model_validate(r_msg.json())
        assert len(env_msg.data) == 1
        assert env_msg.source == ComponentSource.LMS

        # 2. /behavior
        r_beh = await client.get("/api/v1/export/behavior", headers={"X-Component-Key": test_keys["c2"]})
        assert r_beh.status_code == 200
        env_beh = Envelope[List[BehaviorWeeklyRecord]].model_validate(r_beh.json())
        assert len(env_beh.data) == 1

        # 3. /academic
        r_aca = await client.get("/api/v1/export/academic", headers={"X-Component-Key": test_keys["c3"]})
        assert r_aca.status_code == 200
        env_aca = Envelope[List[AcademicRecord]].model_validate(r_aca.json())
        assert len(env_aca.data) == 1

        # 4. /affective
        r_aff = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c3"]})
        assert r_aff.status_code == 200
        env_aff = Envelope[List[AffectiveWeeklyVector]].model_validate(r_aff.json())
        assert len(env_aff.data) == 1

        # 5. /trajectory
        r_trj = await client.get("/api/v1/export/trajectory", headers={"X-Component-Key": test_keys["c3"]})
        assert r_trj.status_code == 200
        env_trj = Envelope[List[EngagementTrajectory]].model_validate(r_trj.json())
        assert len(env_trj.data) == 1

        # 6. /risk
        r_rsk = await client.get("/api/v1/export/risk", headers={"X-Component-Key": test_keys["c4"]})
        assert r_rsk.status_code == 200
        env_rsk = Envelope[List[RiskAssessment]].model_validate(r_rsk.json())
        assert len(env_rsk.data) == 1

        # 7. /outcomes
        r_out = await client.get("/api/v1/export/outcomes", headers={"X-Component-Key": test_keys["c4"]})
        assert r_out.status_code == 200
        env_out = Envelope[List[InterventionOutcome]].model_validate(r_out.json())
        assert len(env_out.data) == 1


# ── TEST 6: Filters, Sorting & Pagination ─────────────────────────────────────

@pytest.mark.asyncio
async def test_readback_filters_and_pagination(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    now = datetime.now(timezone.utc)
    pid = pseudonymize("STU_FILTER_001")
    await setup_student_and_course(db, pid, course_id, consent_decision="accepted")

    # Insert 6 weekly risk records across weeks 0 to 5
    for w in range(6):
        tier = "high" if w >= 3 else "low"
        await db[col.RISK_ASSESSMENTS].insert_one({
            "_id": f"{pid}__{course_id}__{w}",
            "pid": pid,
            "course_id": course_id,
            "week_index": w,
            "risk_score": 0.2 + (w * 0.1),
            "risk_tier": tier,
            "modality_contributions": {"affective": 0.33, "behavioral": 0.33, "academic": 0.34},
            "top_drivers": [],
            "schema_version": 1,
            "ingested_at": now + timedelta(hours=w),
            "source_version": "1.0",
            "source": "ingest",
        })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. page_size > 500 rejected with 422
        r_bad_size = await client.get("/api/v1/export/risk?page_size=501", headers={"X-Component-Key": test_keys["c4"]})
        assert r_bad_size.status_code == 422

        # 2. Invalid PID -> 400
        r_bad_pid = await client.get("/api/v1/export/risk?pid=INVALID_PID_123", headers={"X-Component-Key": test_keys["c4"]})
        assert r_bad_pid.status_code == 400

        # 3. Invalid risk_tier -> 400
        r_bad_tier = await client.get("/api/v1/export/risk?risk_tier=catastrophic", headers={"X-Component-Key": test_keys["c4"]})
        assert r_bad_tier.status_code == 400

        # 4. week_from > week_to -> 400
        r_bad_weeks = await client.get("/api/v1/export/risk?week_from=4&week_to=2", headers={"X-Component-Key": test_keys["c4"]})
        assert r_bad_weeks.status_code == 400

        # 5. Filter by risk_tier='high'
        r_high = await client.get("/api/v1/export/risk?risk_tier=high", headers={"X-Component-Key": test_keys["c4"]})
        assert r_high.status_code == 200
        high_weeks = [item["week_index"] for item in r_high.json()["data"]]
        assert high_weeks == [3, 4, 5]

        # 6. Filter by week range
        r_range = await client.get("/api/v1/export/risk?week_from=1&week_to=3", headers={"X-Component-Key": test_keys["c4"]})
        assert r_range.status_code == 200
        range_weeks = [item["week_index"] for item in r_range.json()["data"]]
        assert range_weeks == [1, 2, 3]

        # 7. Polling with ingested_since
        cutoff = now + timedelta(hours=3, minutes=30)
        r_since = await client.get(
            f"/api/v1/export/risk?ingested_since={cutoff.isoformat()}",
            headers={"X-Component-Key": test_keys["c4"]},
        )
        assert r_since.status_code == 200
        since_weeks = [item["week_index"] for item in r_since.json()["data"]]
        assert since_weeks == [4, 5]

        # 8. Disjoint pagination & stable order
        r_p1 = await client.get("/api/v1/export/risk?page=1&page_size=3", headers={"X-Component-Key": test_keys["c4"]})
        r_p2 = await client.get("/api/v1/export/risk?page=2&page_size=3", headers={"X-Component-Key": test_keys["c4"]})
        assert r_p1.status_code == 200 and r_p2.status_code == 200
        p1_weeks = [item["week_index"] for item in r_p1.json()["data"]]
        p2_weeks = [item["week_index"] for item in r_p2.json()["data"]]
        assert p1_weeks == [0, 1, 2]
        assert p2_weeks == [3, 4, 5]
        assert set(p1_weeks).isdisjoint(set(p2_weeks))


# ── TEST 7: Critical Audit Logging & Forced Failure ───────────────────────────

@pytest.mark.asyncio
async def test_readback_critical_audit(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    pid = pseudonymize("STU_AUDIT_001")
    await setup_student_and_course(db, pid, course_id, consent_decision="accepted")

    now = datetime.now(timezone.utc)
    await db[col.AFFECTIVE_WEEKLY].insert_one({
        "_id": f"{pid}__{course_id}__0",
        "pid": pid,
        "course_id": course_id,
        "week_index": 0,
        "emotion_scores": VALID_EMOTION_SCORES,
        "stress_label": "conceptual_confusion",
        "confidence": 0.9,
        "message_count": 3,
        "top_drivers": [],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "ingest",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Successful read creates EXPORT_GENERATED log with counts and NO data
        r_ok = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c3"]})
        assert r_ok.status_code == 200

        audit_entry = await db[col.AUDIT_LOGS].find_one(
            {"action": AuditAction.EXPORT_GENERATED.value, "target_id": "affective"},
            sort=[("timestamp", -1)],
        )
        assert audit_entry is not None
        assert audit_entry["actor_id"] == "component:c3"
        assert audit_entry["outcome"] == "success"
        assert "row_count" in audit_entry["details"]
        assert "data" not in audit_entry["details"]

        # Forced audit failure returns HTTP 500 and NO data
        with patch("app.services.audit.insert_audit_log", side_effect=RuntimeError("Database audit failure")):
            r_fail = await client.get("/api/v1/export/affective", headers={"X-Component-Key": test_keys["c3"]})
            assert r_fail.status_code == 500


# ── TEST 8: Ingestion to Export Round Trip ─────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_to_export_round_trip(throwaway_readback_db):
    db, test_keys, _, _ = throwaway_readback_db
    course_id = "CS101"
    pid = pseudonymize("STU_ROUNDTRIP")
    await setup_student_and_course(db, pid, course_id, consent_decision="accepted")

    # Ingest payload through REAL /ingest/affective endpoint as C1
    now_iso = datetime.now(timezone.utc).isoformat()
    ingest_payload = {
        "schema_version": "1.0",
        "generated_at": now_iso,
        "source": "c1",
        "request_id": "req_roundtrip_test",
        "data": [
            {
                "pid": pid,
                "course_id": course_id,
                "week_index": 2,
                "emotion_scores": {
                    "exam_anxiety": 0.15,
                    "conceptual_confusion": 0.35,
                    "academic_helplessness": 0.10,
                    "course_frustration": 0.25,
                    "motivation_erosion": 0.15,
                },
                "stress_label": "conceptual_confusion",
                "confidence": 0.94,
                "message_count": 8,
                "top_drivers": [
                    {"token_or_marker": "comprehension", "weight": 0.72},
                ],
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_ingest = await client.post(
            "/api/v1/ingest/affective",
            json=ingest_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert r_ingest.status_code == 200
        assert r_ingest.json()["created"] == 1

        # Read back through /export/affective as C3
        r_read_c3 = await client.get(
            f"/api/v1/export/affective?pid={pid}&week_from=2&week_to=2",
            headers={"X-Component-Key": test_keys["c3"]},
        )
        assert r_read_c3.status_code == 200
        c3_data = r_read_c3.json()["data"]
        assert len(c3_data) == 1
        rec = c3_data[0]

        assert rec["pid"] == pid
        assert rec["course_id"] == course_id
        assert rec["week_index"] == 2
        assert rec["stress_label"] == "conceptual_confusion"
        assert rec["confidence"] == 0.94
        assert rec["message_count"] == 8
        assert rec["emotion_scores"]["conceptual_confusion"] == 0.35
        assert len(rec["top_drivers"]) == 1
        assert rec["top_drivers"][0]["token_or_marker"] == "comprehension"
        assert rec["top_drivers"][0]["weight"] == 0.72

        # Read back through /export/affective as C4
        r_read_c4 = await client.get(
            f"/api/v1/export/affective?pid={pid}&week_from=2&week_to=2",
            headers={"X-Component-Key": test_keys["c4"]},
        )
        assert r_read_c4.status_code == 200
        assert len(r_read_c4.json()["data"]) == 1


# ── TEST 9: Strictly Read-Only ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_readback_strictly_read_only(throwaway_readback_db):
    """Asserts that no mutation methods (POST, PUT, DELETE, PATCH) exist on readback routes."""
    _, test_keys, _, _ = throwaway_readback_db
    endpoints = ["/api/v1/export/affective", "/api/v1/export/trajectory", "/api/v1/export/risk", "/api/v1/export/outcomes"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c4"]}
        for ep in endpoints:
            assert (await client.post(ep, headers=headers)).status_code == 405
            assert (await client.put(ep, headers=headers)).status_code == 405
            assert (await client.delete(ep, headers=headers)).status_code == 405
            assert (await client.patch(ep, headers=headers)).status_code == 405
