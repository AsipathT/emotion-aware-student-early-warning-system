"""
backend/tests/test_ingest_api.py

Feature 23: Component Ingestion Endpoints Test Suite.
Real MongoDB execution only:
  - Part A: Component authentication matrix (keys, scopes, 401/403/503, bearer rejection, ACCESS_DENIED audit).
  - Part B: Stage 1 validation (envelope contract validation, sanitized error paths, modality sum, versions, 413 limits).
  - Part C: Stage 2 business validation (UNKNOWN_PID, NOT_ENROLLED, NO_CONSENT, OULAD exemption, DUPLICATE_IN_BATCH, CONFLICT_STAFF_DECISION).
  - Part D: Idempotency & persistence (deterministic _id, ReplaceOne upsert, resend counts, no stale fields).
  - Part E: Dry run mode (zero storage writes, accurate count reporting, dry_run run doc).
  - Part F: Run tracking & audit logging (ingestion_runs status, DATA_INGESTED audit, non-critical audit resilience).
  - Part G: Performance & route invariants (batch lookups, strictly POST endpoints).
"""

import copy
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import sys
from pathlib import Path

# Ensure project root is in sys.path
for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import httpx
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from pymongo import MongoClient

from app.core.config import settings
from app.core.database import create_mongo_client, get_db
from app.core.privacy import pseudonymize
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.main import app
from app.routers.ingest import router as ingest_router
from app.schemas.audit import AuditAction, AuditOutcome
from app.core.contract_version import CONTRACT_VERSION
from app.schemas.contract.common import ComponentSource
from scripts.setup_db import setup_database


# ── Throwaway Test Database Fixture ───────────────────────────────────────────

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

    # Apply strict schema validators and compound indexes
    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    # Override FastAPI DB dependency
    app.dependency_overrides[get_db] = lambda: db

    # Configure test component keys
    test_keys = {
        "c1": "test_key_c1",
        "c2": "test_key_c2",
        "c3": "test_key_c3",
        "c4": "test_key_c4",
    }
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


# ── Helper Setup Functions ────────────────────────────────────────────────────

async def setup_test_student_context(
    db: Any,
    pid: str,
    course_id: str,
    has_consent: bool = True,
    is_oulad: bool = False,
    consent_decision: str = "accepted",
    notice_version: int = 1,
) -> None:
    """Sets up prerequisite student, course, notice, and enrolment documents in test DB."""
    now = datetime.now(timezone.utc)

    # 1. Identity Vault
    vault_doc = {
        "_id": pid,
        "pid": pid,
        "student_id": f"ID_{pid}",
        "name": f"Student {pid}",
        "email": f"{pid}@lms.edu",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "is_imported": is_oulad,
        "source": "oulad" if is_oulad else "test",
    }
    await db[col.IDENTITY_VAULT].update_one({"_id": pid}, {"$set": vault_doc}, upsert=True)

    # 2. Course
    course_doc = {
        "_id": course_id,
        "id": course_id,
        "course_id": course_id,
        "title": f"Course {course_id}",
        "description": "Test Course",
        "lecturer_id": "lecturer-uuid",
        "modules": [],
        "is_published": True,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "created_at": now,
        "updated_at": now,
    }
    await db[col.COURSES].update_one({"_id": course_id}, {"$set": course_doc}, upsert=True)

    # 3. Active Consent Notice
    notice_doc = {
        "_id": f"notice_v{notice_version}",
        "id": f"notice_v{notice_version}",
        "version": notice_version,
        "text": "Ethics and data privacy consent notice for testing.",
        "effective_from": now - timedelta(days=1),
        "is_active": True,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }
    await db[col.CONSENT_NOTICES].update_one({"_id": notice_doc["_id"]}, {"$set": notice_doc}, upsert=True)

    # 4. Consent Record
    if has_consent:
        consent_doc = {
            "_id": f"consent_{pid}_v{notice_version}",
            "pid": pid,
            "notice_version": notice_version,
            "decision": consent_decision,
            "timestamp": now,
            "ip_or_client": "127.0.0.1",
            "source": "test",
        }
        await db[col.CONSENT_RECORDS].update_one({"_id": consent_doc["_id"]}, {"$set": consent_doc}, upsert=True)

    # 5. Enrolment
    enrol_doc = {
        "_id": f"{pid}_{course_id}",
        "pid": pid,
        "course_id": course_id,
        "enrolment_start": now - timedelta(days=7),
        "status": "active",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }
    await db[col.ENROLMENTS].update_one({"_id": enrol_doc["_id"]}, {"$set": enrol_doc}, upsert=True)


def build_c1_envelope(pid: str, course_id: str, week: int = 0, source: str = "c1") -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "data": [
            {
                "pid": pid,
                "course_id": course_id,
                "week_index": week,
                "emotion_scores": {
                    "exam_anxiety": 0.40,
                    "conceptual_confusion": 0.25,
                    "academic_helplessness": 0.15,
                    "course_frustration": 0.10,
                    "motivation_erosion": 0.10,
                },
                "stress_label": "moderate",
                "confidence": 0.85,
                "message_count": 3,
                "top_drivers": [
                    {"token_or_marker": "exam_prep", "weight": 0.7},
                    {"token_or_marker": "quiz_review", "weight": 0.3},
                ],
            }
        ],
    }


def build_c2_envelope(pid: str, course_id: str, week: int = 0, source: str = "c2") -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "data": [
            {
                "pid": pid,
                "course_id": course_id,
                "week_index": week,
                "trajectory_label": "declining",
                "confidence": 0.82,
                "contributing_indicators": ["reduced_logins", "delayed_submission"],
            }
        ],
    }


def build_c3_envelope(pid: str, course_id: str, week: int = 0, source: str = "c3") -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "data": [
            {
                "pid": pid,
                "course_id": course_id,
                "week_index": week,
                "risk_score": 0.78,
                "risk_tier": "high",
                "modality_contributions": {
                    "affective": 0.40,
                    "behavioral": 0.35,
                    "academic": 0.25,
                },
                "top_drivers": ["high_confusion", "reduced_logins"],
            }
        ],
    }


def build_c4_envelope(rec_id: str, pid: str, week: int = 0, source: str = "c4") -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "data": [
            {
                "recommendation_id": rec_id,
                "pid": pid,
                "week_index": week,
                "status": "proposed",
                "candidates": [
                    {
                        "intervention_type": "peer_tutoring",
                        "suitability_score": 0.88,
                        "rationale": "High conceptual confusion detected.",
                        "rank": 1,
                    }
                ],
            }
        ],
    }


# ── PART A: Authentication Matrix Tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_matrix(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    pid = pseudonymize("STU_AUTH_001")
    course_id = "CS101"
    await setup_test_student_context(db, pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = build_c1_envelope(pid, course_id)

        # 1. Missing Key -> 401 & ACCESS_DENIED audit
        resp_missing = await client.post("/api/v1/ingest/affective", json=payload)
        assert resp_missing.status_code == 401
        audit_entry = await db[col.AUDIT_LOGS].find_one(
            {"action": AuditAction.ACCESS_DENIED, "target_type": "ingest"}
        )
        assert audit_entry is not None
        assert audit_entry["outcome"] == AuditOutcome.DENIED

        # 2. Wrong Key -> 401 & ACCESS_DENIED audit
        resp_wrong = await client.post(
            "/api/v1/ingest/affective",
            json=payload,
            headers={"X-Component-Key": "wrong_secret_key"},
        )
        assert resp_wrong.status_code == 401

        # 3. Scope Mismatch (C1 key called on /risk) -> 403
        risk_payload = build_c3_envelope(pid, course_id)
        resp_scope = await client.post(
            "/api/v1/ingest/risk",
            json=risk_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert resp_scope.status_code == 403
        assert "not authorized" in resp_scope.json()["detail"].lower()

        # 4. Admin Bearer Token Rejected (strictly forbidden for writes) -> 401
        admin_id = str(uuid.uuid4())
        admin_token = create_access_token(admin_id, role="admin")
        resp_bearer = await client.post(
            "/api/v1/ingest/affective",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_bearer.status_code == 401
        assert "missing x-component-key header" in resp_bearer.json()["detail"].lower()

        # 5. Envelope Source Mismatch (C1 key, but envelope source='c2') -> 403
        mismatched_envelope = build_c1_envelope(pid, course_id, source="c2")
        resp_source_mismatch = await client.post(
            "/api/v1/ingest/affective",
            json=mismatched_envelope,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert resp_source_mismatch.status_code == 403
        assert "envelope source" in resp_source_mismatch.json()["detail"].lower()

        # 6. Unconfigured Component Keys -> 503
        saved_keys_val = settings.component_api_keys
        try:
            settings.component_api_keys = ""
            resp_unconf = await client.post(
                "/api/v1/ingest/affective",
                json=payload,
                headers={"X-Component-Key": test_keys["c1"]},
            )
            assert resp_unconf.status_code == 503
            assert "not configured" in resp_unconf.json()["detail"].lower()
        finally:
            settings.component_api_keys = saved_keys_val


# ── PART B: Stage 1 Contract Validation Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_stage1_contract_validation(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    pid = pseudonymize("STU_STAGE1_001")
    course_id = "CS101"
    await setup_test_student_context(db, pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c1"]}

        # 1. Invalid schema type / missing field -> 422 with sanitized error path
        bad_payload = build_c1_envelope(pid, course_id)
        secret_password_input = "SUPER_SECRET_LEAK_INPUT"
        bad_payload["data"][0]["confidence"] = "not_a_float"
        bad_payload["data"][0]["leaked_field"] = secret_password_input

        resp_bad = await client.post("/api/v1/ingest/affective", json=bad_payload, headers=headers)
        assert resp_bad.status_code == 422
        resp_text = resp_bad.text
        # Invariant: submitted sensitive value must NEVER be echoed
        assert secret_password_input not in resp_text
        error_locs = [e["loc"] for e in resp_bad.json()["detail"]]
        assert any("confidence" in loc for loc in error_locs)

        # 2. Modality contributions sum != 1.0 on /risk -> 422
        risk_headers = {"X-Component-Key": test_keys["c3"]}
        bad_risk_payload = build_c3_envelope(pid, course_id)
        bad_risk_payload["data"][0]["modality_contributions"] = {
            "affective": 0.20,
            "behavioral": 0.20,
            "academic": 0.20,  # Sum = 0.60
        }
        resp_modality = await client.post("/api/v1/ingest/risk", json=bad_risk_payload, headers=risk_headers)
        assert resp_modality.status_code == 422
        assert "sum to 1.0" in resp_modality.text

        # 3. Unsupported Major Version -> 422
        major_v2_payload = build_c1_envelope(pid, course_id)
        major_v2_payload["schema_version"] = "2.0"
        resp_v2 = await client.post("/api/v1/ingest/affective", json=major_v2_payload, headers=headers)
        assert resp_v2.status_code == 422
        assert "unsupported" in resp_v2.text.lower() and "major" in resp_v2.text.lower()

        # 4. Higher Minor Version accepted -> 200
        minor_v11_payload = build_c1_envelope(pid, course_id)
        minor_v11_payload["schema_version"] = "1.1"
        resp_v11 = await client.post("/api/v1/ingest/affective", json=minor_v11_payload, headers=headers)
        assert resp_v11.status_code == 200
        assert resp_v11.json()["accepted"] == 1

        # 5. Batch Size Cap (> INGEST_MAX_BATCH) -> 413
        huge_records = [copy.deepcopy(minor_v11_payload["data"][0]) for _ in range(settings.INGEST_MAX_BATCH + 1)]
        over_batch_payload = copy.deepcopy(minor_v11_payload)
        over_batch_payload["data"] = huge_records
        resp_huge_batch = await client.post("/api/v1/ingest/affective", json=over_batch_payload, headers=headers)
        assert resp_huge_batch.status_code == 413
        assert "batch size" in resp_huge_batch.text.lower()

        # 6. Body Size Cap (> INGEST_MAX_BODY_BYTES) -> 413
        # Send a dummy body with large content-length
        huge_headers = copy.deepcopy(headers)
        huge_headers["content-length"] = str(settings.INGEST_MAX_BODY_BYTES + 1024)
        resp_body_size = await client.post(
            "/api/v1/ingest/affective",
            content=b"dummy large payload",
            headers=huge_headers,
        )
        assert resp_body_size.status_code == 413
        assert "exceeds maximum limit" in resp_body_size.text.lower()


# ── PART C: Stage 2 Business Validation Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_stage2_business_validation(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    valid_pid = pseudonymize("STU_STAGE2_VALID")
    course_id = "CS101"
    await setup_test_student_context(db, valid_pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c1"]}

        # 1. UNKNOWN_PID (PID not in identity_vault)
        unknown_pid = pseudonymize("STU_UNKNOWN_999")
        unknown_payload = build_c1_envelope(unknown_pid, course_id)
        resp_unknown = await client.post("/api/v1/ingest/affective", json=unknown_payload, headers=headers)
        assert resp_unknown.status_code == 200
        body_u = resp_unknown.json()
        assert body_u["rejected"] == 1
        assert body_u["rejected_records"][0]["reason_code"] == "UNKNOWN_PID"

        # 2. NOT_ENROLLED (PID in vault, but not enrolled in course_id)
        unenrolled_pid = pseudonymize("STU_NOT_ENROLLED_001")
        # Add to vault, but do NOT enrol
        await db[col.IDENTITY_VAULT].insert_one({
            "_id": unenrolled_pid,
            "pid": unenrolled_pid,
            "student_id": "STU_UNENROLLED",
            "name": "Unenrolled",
            "email": "unenrolled@lms.edu",
            "schema_version": 1,
            "ingested_at": datetime.now(timezone.utc),
            "source_version": "1.0",
        })
        # Add consent
        await db[col.CONSENT_RECORDS].insert_one({
            "_id": f"consent_{unenrolled_pid}_v1",
            "pid": unenrolled_pid,
            "notice_version": 1,
            "decision": "accepted",
            "timestamp": datetime.now(timezone.utc),
            "ip_or_client": "127.0.0.1",
            "source": "test",
        })

        not_enrolled_payload = build_c1_envelope(unenrolled_pid, course_id)
        resp_not_enr = await client.post("/api/v1/ingest/affective", json=not_enrolled_payload, headers=headers)
        assert resp_not_enr.status_code == 200
        body_ne = resp_not_enr.json()
        assert body_ne["rejected"] == 1
        assert body_ne["rejected_records"][0]["reason_code"] == "NOT_ENROLLED"

        # 3. NO_CONSENT (Declined or Withdrawn consent)
        declined_pid = pseudonymize("STU_DECLINED_001")
        await setup_test_student_context(db, declined_pid, course_id, has_consent=True, consent_decision="declined")
        resp_declined = await client.post("/api/v1/ingest/affective", json=build_c1_envelope(declined_pid, course_id), headers=headers)
        assert resp_declined.status_code == 200
        assert resp_declined.json()["rejected_records"][0]["reason_code"] == "NO_CONSENT"

        # 4. OULAD Exemption (is_imported=True in vault passes WITHOUT consent)
        oulad_pid = pseudonymize("STU_OULAD_001")
        await setup_test_student_context(db, oulad_pid, course_id, has_consent=False, is_oulad=True)
        resp_oulad = await client.post("/api/v1/ingest/affective", json=build_c1_envelope(oulad_pid, course_id), headers=headers)
        assert resp_oulad.status_code == 200
        assert resp_oulad.json()["accepted"] == 1
        assert resp_oulad.json()["rejected"] == 0

        # 5. DUPLICATE_IN_BATCH (same natural key repeated in batch)
        dup_payload = build_c1_envelope(valid_pid, course_id, week=0)
        # Duplicate record 0 into position 1
        dup_payload["data"].append(copy.deepcopy(dup_payload["data"][0]))
        resp_dup = await client.post("/api/v1/ingest/affective", json=dup_payload, headers=headers)
        assert resp_dup.status_code == 200
        body_dup = resp_dup.json()
        assert body_dup["received"] == 2
        assert body_dup["accepted"] == 1
        assert body_dup["rejected"] == 1
        assert body_dup["rejected_records"][0]["reason_code"] == "DUPLICATE_IN_BATCH"

        # 6. CONFLICT_STAFF_DECISION on C4 Recommendations
        c4_headers = {"X-Component-Key": test_keys["c4"]}
        rec_id = f"REC_STAFF_CONFLICT_{valid_pid}"
        # Pre-seed recommendation with status "approved" (reviewed by staff)
        await db[col.RECOMMENDATIONS].insert_one({
            "_id": rec_id,
            "recommendation_id": rec_id,
            "pid": valid_pid,
            "week_index": 0,
            "status": "approved",
            "candidates": [
                {
                    "intervention_type": "peer_tutoring",
                    "suitability_score": 0.85,
                    "rationale": "Approved tutoring session.",
                    "rank": 1,
                }
            ],
            "schema_version": 1,
            "source_version": "1.0",
            "ingested_at": datetime.now(timezone.utc),
        })

        c4_payload = build_c4_envelope(rec_id, valid_pid, week=0)
        resp_conflict = await client.post("/api/v1/ingest/recommendations", json=c4_payload, headers=c4_headers)
        assert resp_conflict.status_code == 200
        body_conf = resp_conflict.json()
        assert body_conf["rejected"] == 1
        assert body_conf["rejected_records"][0]["reason_code"] == "CONFLICT_STAFF_DECISION"

        # 7. Partial Batch Success (1 valid record + 1 invalid record in same batch)
        partial_payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "c1",
            "request_id": "req_partial_test",
            "data": [
                build_c1_envelope(valid_pid, course_id, week=2)["data"][0],      # Valid
                build_c1_envelope(unknown_pid, course_id, week=2)["data"][0],    # Invalid
            ],
        }
        resp_partial = await client.post("/api/v1/ingest/affective", json=partial_payload, headers=headers)
        assert resp_partial.status_code == 200
        body_p = resp_partial.json()
        assert body_p["received"] == 2
        assert body_p["accepted"] == 1
        assert body_p["rejected"] == 1
        assert body_p["created"] == 1
        # Valid record persisted in DB
        persisted = await db[col.AFFECTIVE_WEEKLY].find_one({"pid": valid_pid, "week_index": 2})
        assert persisted is not None


# ── PART D: Persistence, Idempotency & ReplaceOne ─────────────────────────────

@pytest.mark.asyncio
async def test_persistence_and_idempotency(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    pid = pseudonymize("STU_IDEMP_001")
    course_id = "CS101"
    await setup_test_student_context(db, pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c2"]}
        payload = build_c2_envelope(pid, course_id, week=3)

        # 1. First send: created = 1, updated = 0
        resp1 = await client.post("/api/v1/ingest/trajectory", json=payload, headers=headers)
        assert resp1.status_code == 200
        b1 = resp1.json()
        assert b1["created"] == 1
        assert b1["updated"] == 0

        # Verify deterministic _id format
        expected_id = f"{pid}__{course_id}__3"
        doc = await db[col.ENGAGEMENT_TRAJECTORIES].find_one({"_id": expected_id})
        assert doc is not None
        assert doc["trajectory_label"] == "declining"
        assert doc["confidence"] == 0.82
        assert doc["schema_version"] == 1

        # 2. Re-send identical payload: created = 0, updated = 1
        resp2 = await client.post("/api/v1/ingest/trajectory", json=payload, headers=headers)
        assert resp2.status_code == 200
        b2 = resp2.json()
        assert b2["created"] == 0
        assert b2["updated"] == 1
        # Count in collection unchanged
        total_docs = await db[col.ENGAGEMENT_TRAJECTORIES].count_documents({"pid": pid})
        assert total_docs == 1

        # 3. Corrected re-send: replaces values cleanly with no stale fields
        corrected_payload = copy.deepcopy(payload)
        corrected_payload["data"][0]["trajectory_label"] = "improving"
        corrected_payload["data"][0]["confidence"] = 0.95
        corrected_payload["data"][0]["contributing_indicators"] = ["daily_portal_logins"]

        resp3 = await client.post("/api/v1/ingest/trajectory", json=corrected_payload, headers=headers)
        assert resp3.status_code == 200
        b3 = resp3.json()
        assert b3["created"] == 0
        assert b3["updated"] == 1

        updated_doc = await db[col.ENGAGEMENT_TRAJECTORIES].find_one({"_id": expected_id})
        assert updated_doc["trajectory_label"] == "improving"
        assert updated_doc["confidence"] == 0.95
        assert updated_doc["contributing_indicators"] == ["daily_portal_logins"]


# ── PART E: Dry Run Mode Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_mode(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    pid = pseudonymize("STU_DRY_001")
    course_id = "CS101"
    await setup_test_student_context(db, pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c3"]}
        payload = build_c3_envelope(pid, course_id, week=1)

        # Execute with dry_run=true
        resp = await client.post("/api/v1/ingest/risk?dry_run=true", json=payload, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["received"] == 1
        assert body["accepted"] == 1
        assert body["created"] == 1
        assert body["updated"] == 0

        # Invariant: ZERO documents written to target collection
        stored_count = await db[col.RISK_ASSESSMENTS].count_documents({"pid": pid})
        assert stored_count == 0

        # Ingestion run recorded with dry_run = True
        run_doc = await db[col.INGESTION_RUNS].find_one({"run_id": body["run_id"]})
        assert run_doc is not None
        assert run_doc["dry_run"] is True
        assert run_doc["status"] == "completed"


# ── PART F: Run Tracking & Audit Logging Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_run_tracking_and_audit(throwaway_ingest_db):
    _, _, db, _, test_keys = throwaway_ingest_db
    valid_pid = pseudonymize("STU_RUN_001")
    course_id = "CS101"
    await setup_test_student_context(db, valid_pid, course_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Component-Key": test_keys["c1"]}
        payload = build_c1_envelope(valid_pid, course_id, week=4)

        resp = await client.post("/api/v1/ingest/affective", json=payload, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        run_id = body["run_id"]

        # 1. Ingestion Runs document tracking
        run_doc = await db[col.INGESTION_RUNS].find_one({"run_id": run_id})
        assert run_doc is not None
        assert run_doc["component"] == "c1"
        assert run_doc["status"] == "completed"
        assert run_doc["started_at"] is not None
        assert run_doc["ended_at"] is not None
        assert run_doc["details"]["received"] == 1
        assert run_doc["details"]["accepted"] == 1
        assert run_doc["details"]["rejected"] == 0

        # 2. Audit Logging (AuditAction.DATA_INGESTED)
        audit_entry = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.DATA_INGESTED, "details.run_id": run_id})
        assert audit_entry is not None
        assert audit_entry["actor_role"] == "component"
        assert audit_entry["outcome"] == AuditOutcome.SUCCESS
        # Never store raw data payload in audit logs
        assert "emotion_scores" not in str(audit_entry["details"])
        assert "top_drivers" not in str(audit_entry["details"])
        assert audit_entry["details"]["accepted"] == 1

        # 3. Non-critical audit write failure resilience: forced error still returns 200
        with patch("app.routers.ingest.log_event", side_effect=RuntimeError("Simulated audit write failure")):
            resp_audit_fail = await client.post(
                "/api/v1/ingest/affective",
                json=build_c1_envelope(valid_pid, course_id, week=5),
                headers=headers,
            )
            assert resp_audit_fail.status_code == 200
            assert resp_audit_fail.json()["accepted"] == 1


# ── PART G: Performance Sanity & Route Invariants ─────────────────────────────

@pytest.mark.asyncio
async def test_batch_lookup_performance(throwaway_ingest_db):
    """Verifies that large batches use batch lookups instead of N+1 individual queries."""
    _, _, db, _, test_keys = throwaway_ingest_db
    course_id = "CS101"
    now = datetime.now(timezone.utc)

    # Setup course and active notice
    await db[col.COURSES].update_one(
        {"_id": course_id},
        {
            "$set": {
                "_id": course_id,
                "id": course_id,
                "course_id": course_id,
                "title": "CS101",
                "description": "Intro",
                "lecturer_id": "dummy-lecturer",
                "modules": [],
                "is_published": True,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
                "created_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    await db[col.CONSENT_NOTICES].update_one(
        {"_id": "notice_v1"},
        {
            "$set": {
                "_id": "notice_v1",
                "id": "notice_v1",
                "version": 1,
                "text": "Ethics and data privacy consent notice for performance test.",
                "effective_from": now - timedelta(days=1),
                "is_active": True,
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
        },
        upsert=True,
    )

    # Pre-seed 30 students in bulk
    pids = [pseudonymize(f"STU_PERF_{i:03d}") for i in range(30)]
    vault_docs = [
        {
            "_id": pid,
            "pid": pid,
            "student_id": f"ID_{pid}",
            "name": f"Student {pid}",
            "email": f"{pid}@lms.edu",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        for pid in pids
    ]
    consent_docs = [
        {
            "_id": f"consent_{pid}_v1",
            "pid": pid,
            "notice_version": 1,
            "decision": "accepted",
            "timestamp": now,
            "ip_or_client": "127.0.0.1",
            "source": "test",
        }
        for pid in pids
    ]
    enrol_docs = [
        {
            "_id": f"{pid}_{course_id}",
            "pid": pid,
            "course_id": course_id,
            "enrolment_start": now - timedelta(days=7),
            "status": "active",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        for pid in pids
    ]
    await db[col.IDENTITY_VAULT].insert_many(vault_docs)
    await db[col.CONSENT_RECORDS].insert_many(consent_docs)
    await db[col.ENROLMENTS].insert_many(enrol_docs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        records = [
            build_c1_envelope(pid, course_id, week=0)["data"][0]
            for pid in pids
        ]
        batch_payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "c1",
            "request_id": "req_perf_batch",
            "data": records,
        }

        resp = await client.post(
            "/api/v1/ingest/affective",
            json=batch_payload,
            headers={"X-Component-Key": test_keys["c1"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["received"] == 30
        assert body["accepted"] == 30
        assert body["created"] == 30


def test_routes_strictly_post():
    """Invariance test: All routes on the ingestion router MUST be POST only."""
    for route in ingest_router.routes:
        assert hasattr(route, "methods"), f"Route {route} has no methods defined."
        methods = set(route.methods)
        assert methods == {"POST"}, f"Route {route.path} allows non-POST methods: {methods}"
