"""
backend/tests/test_pipeline.py

Feature 22: Weekly Scheduler & Pipeline Orchestrator Unit and Integration Test Suite.
Verifies:
  - Part A: Injectable clock & distributed lease locking (takeover on expiry, safe release)
  - Part B: Due week discovery (grace cutoff, lookback window, source exclusions, deduplication)
  - Part C: Pipeline run creation and idempotency
  - Part D: Set-based coverage calculations (C1-C4, risk tier filtering, zero-eligible handling)
  - Part E: Stage state machine & progression (dependencies, coverage thresholds, timeouts, audit logs)
  - Part F: Webhook HMAC-SHA256 signature and retry dispatch
  - Part G: Orchestrator tick runner and dry-run mode
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import pytest
import pytest_asyncio
from pymongo import MongoClient

from app.core.config import settings
from app.core.database import create_mongo_client
from app.db import collections as col
from app.pipeline.advance import advance_pipeline_run
from app.pipeline.clock import get_clock, reset_clock, set_clock
from app.pipeline.coverage import compute_stage_coverage, get_eligible_course_pids
from app.pipeline.discovery import create_pipeline_run, find_due_weeks
from app.pipeline.lock import acquire_lock, heartbeat_lock, release_lock
from app.pipeline.orchestrator import run_pipeline_tick
from app.pipeline.stages import clear_stage_handlers, register_stage_handler
from app.pipeline.webhooks import dispatch_stage_ready_webhook, sign_payload
from app.schemas.audit import AuditAction
from scripts.setup_db import setup_database


# ── Throwaway Test Database Fixture ───────────────────────────────────────────

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

    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    yield uri, test_db_name, db

    reset_clock()
    clear_stage_handlers()
    # Re-register default handler after test
    from app.pipeline.stages import default_lms_aggregation_handler
    register_stage_handler("lms_aggregation", default_lms_aggregation_handler)

    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


# ── Helper Setup Functions ────────────────────────────────────────────────────

async def setup_test_course_and_consent(
    db: Any,
    course_id: str,
    pids: List[str],
    week_index: int = 1,
    course_source: str = "internal",
    start_offset_days: int = 14,
    end_offset_days: int = 7,
    now: datetime = None,
) -> None:
    """Creates course, course_week, students in identity_vault, active consent, and enrolments."""
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Course
    await db[col.COURSES].insert_one({
        "_id": f"crs_{course_id}",
        "course_id": course_id,
        "title": f"Test Course {course_id}",
        "source": course_source,
        "is_published": True,
        "created_at": now,
        "updated_at": now,
    })

    # 2. Course Week
    week_start = now - timedelta(days=start_offset_days)
    week_end = now - timedelta(days=end_offset_days)
    await db[col.COURSE_WEEKS].insert_one({
        "_id": f"cw_{course_id}_{week_index}",
        "course_id": course_id,
        "week_index": week_index,
        "title": f"Week {week_index}",
        "start_date": week_start,
        "end_date": week_end,
    })

    # 3. Active Consent Notice
    await db[col.CONSENT_NOTICES].delete_many({})
    await db[col.CONSENT_NOTICES].insert_one({
        "_id": "notice_v1",
        "version": 1,
        "text": "Standard testing consent notice requirement text.",
        "effective_from": now - timedelta(days=30),
        "is_active": True,
    })

    # 4. Identity Vault, Consent Record, and Enrolment for each student
    for pid in pids:
        await db[col.IDENTITY_VAULT].update_one(
            {"_id": pid},
            {"$set": {
                "pid": pid,
                "student_id": f"IT{pid[-8:]}",
                "name": "Test Student",
                "email": f"test_{pid}@university.edu",
                "is_imported": (course_source == "oulad"),
                "source": course_source,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True,
        )

        if course_source != "oulad":
            await db[col.CONSENT_RECORDS].update_one(
                {"pid": pid, "notice_version": 1},
                {"$set": {
                    "decision": "accepted",
                    "timestamp": now - timedelta(days=20),
                }},
                upsert=True,
            )

        await db[col.ENROLMENTS].update_one(
            {"course_id": course_id, "pid": pid},
            {"$set": {
                "status": "active",
                "enrolment_start": week_start - timedelta(days=5),
            }},
            upsert=True,
        )


# ── Part A: Clock and Distributed Lock Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_clock_freeze_and_reset():
    """Verifies that the injectable clock freezes time deterministically."""
    frozen_dt = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(frozen_dt)
    assert get_clock() == frozen_dt
    reset_clock()
    assert abs((get_clock() - datetime.now(timezone.utc)).total_seconds()) < 5


@pytest.mark.asyncio
async def test_distributed_lock_lifecycle(throwaway_pipeline_db):
    """Verifies atomic lease acquisition, exclusion, expiration takeover, and release."""
    _, _, db = throwaway_pipeline_db
    t0 = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    set_clock(t0)

    # 1. Worker 1 acquires lock
    acq1 = await acquire_lock(db, key="test_lock", owner_id="worker_1", lease_seconds=60, now=t0)
    assert acq1 is True

    # 2. Worker 2 attempts while lease active -> rejected
    acq2 = await acquire_lock(db, key="test_lock", owner_id="worker_2", lease_seconds=60, now=t0)
    assert acq2 is False

    # 3. Time advances past lease expiry (t0 + 70s)
    t1 = t0 + timedelta(seconds=70)
    set_clock(t1)

    # 4. Worker 2 takes over expired lease
    acq2_takeover = await acquire_lock(db, key="test_lock", owner_id="worker_2", lease_seconds=60, now=t1)
    assert acq2_takeover is True

    # 5. Worker 2 releases lock
    rel = await release_lock(db, key="test_lock", owner_id="worker_2")
    assert rel is True

    # 6. Worker 1 can immediately re-acquire after release
    acq1_again = await acquire_lock(db, key="test_lock", owner_id="worker_1", lease_seconds=60, now=t1)
    assert acq1_again is True


# ── Part B: Due Week Discovery Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_due_weeks_filtering(throwaway_pipeline_db):
    """Verifies discovery applies grace cutoff, lookback window, source exclusions, and deduplication."""
    _, _, db = throwaway_pipeline_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(now)

    pids = ["STU_1111aaaa", "STU_2222bbbb"]

    # Course 1: Finished 3 hours ago (past 1h grace, within 2w lookback) -> DUE
    await setup_test_course_and_consent(db, "CS101", pids, week_index=1, end_offset_days=0, now=now)
    # Set week_end explicitly to 3 hours ago
    await db[col.COURSE_WEEKS].update_one(
        {"course_id": "CS101", "week_index": 1},
        {"$set": {"end_date": now - timedelta(hours=3)}}
    )

    # Course 2: Finished 30 minutes ago (within 1h grace) -> NOT DUE
    await setup_test_course_and_consent(db, "CS102", pids, week_index=1, end_offset_days=0, now=now)
    await db[col.COURSE_WEEKS].update_one(
        {"course_id": "CS102", "week_index": 1},
        {"$set": {"end_date": now - timedelta(minutes=30)}}
    )

    # Course 3: Finished 3 weeks ago (older than 2-week lookback) -> NOT DUE
    await setup_test_course_and_consent(db, "CS103", pids, week_index=1, end_offset_days=25, now=now)

    # Course 4: Source is 'oulad' -> EXCLUDED by default
    await setup_test_course_and_consent(db, "OULAD1", pids, week_index=1, course_source="oulad", now=now)
    await db[col.COURSE_WEEKS].update_one(
        {"course_id": "OULAD1", "week_index": 1},
        {"$set": {"end_date": now - timedelta(hours=3)}}
    )

    due = await find_due_weeks(db, now=now)
    due_course_ids = [d["course_id"] for d in due]

    assert due_course_ids == ["CS101"]

    # If include_sources allows oulad
    due_with_oulad = await find_due_weeks(db, now=now, excluded_sources=[])
    due_with_oulad_ids = {d["course_id"] for d in due_with_oulad}
    assert "CS101" in due_with_oulad_ids
    assert "OULAD1" in due_with_oulad_ids


# ── Part C: Run Creation & Idempotency Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_create_pipeline_run_idempotency(throwaway_pipeline_db):
    """Verifies pipeline_runs creation idempotency and initial stage structure."""
    _, _, db = throwaway_pipeline_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    week_end = now - timedelta(hours=2)

    doc1 = await create_pipeline_run(db, "CS101", 1, week_end=week_end, now=now)
    assert doc1 is not None
    assert doc1["course_id"] == "CS101"
    assert doc1["week_index"] == 1
    assert doc1["status"] == "pending"
    assert set(doc1["stages"].keys()) == {"lms_aggregation", "c1", "c2", "c3", "c4"}
    assert all(st["status"] == "waiting" for st in doc1["stages"].values())

    # Second creation with identical (course_id, week_index) returns None without crashing
    doc2 = await create_pipeline_run(db, "CS101", 1, week_end=week_end, now=now)
    assert doc2 is None


# ── Part D: Coverage Calculation Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_coverage_calculation(throwaway_pipeline_db):
    """Verifies set-based coverage ratios and C4 risk tier filtering."""
    _, _, db = throwaway_pipeline_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    pids = [f"STU_{i:04d}abcd" for i in range(10)]

    await setup_test_course_and_consent(db, "CS101", pids, week_index=1, now=now)

    eligible = await get_eligible_course_pids(db, "CS101", 1)
    assert len(eligible) == 10

    # Ingest 9 records into affective_weekly (90% coverage)
    for p in pids[:9]:
        await db[col.AFFECTIVE_WEEKLY].insert_one({
            "pid": p,
            "course_id": "CS101",
            "week_index": 1,
            "emotion_scores": {"exam_anxiety": 0.5},
            "stress_label": "moderate",
            "confidence": 0.85,
            "message_count": 3,
            "top_drivers": [],
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })

    cov_c1 = await compute_stage_coverage(db, "c1", "CS101", 1, eligible_pids=eligible)
    assert cov_c1.eligible == 10
    assert cov_c1.received == 9
    assert cov_c1.coverage == 0.9

    # C4 test: Set 2 students at HIGH and MEDIUM risk in risk_assessments
    await db[col.RISK_ASSESSMENTS].insert_one({
        "pid": pids[0],
        "course_id": "CS101",
        "week_index": 1,
        "risk_score": 0.8,
        "risk_tier": "high",
        "modality_contributions": {"affective": 0.4, "behavioral": 0.3, "academic": 0.3},
        "top_drivers": ["drop_in_submissions"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })
    await db[col.RISK_ASSESSMENTS].insert_one({
        "pid": pids[1],
        "course_id": "CS101",
        "week_index": 1,
        "risk_score": 0.6,
        "risk_tier": "medium",
        "modality_contributions": {"affective": 0.4, "behavioral": 0.3, "academic": 0.3},
        "top_drivers": ["exam_anxiety"],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })
    # Low risk student should NOT count toward C4 eligible
    await db[col.RISK_ASSESSMENTS].insert_one({
        "pid": pids[2],
        "course_id": "CS101",
        "week_index": 1,
        "risk_score": 0.1,
        "risk_tier": "low",
        "modality_contributions": {"affective": 0.1, "behavioral": 0.1, "academic": 0.1},
        "top_drivers": [],
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })

    # C4 should have 2 eligible students
    cov_c4_before = await compute_stage_coverage(db, "c4", "CS101", 1, eligible_pids=eligible)
    assert cov_c4_before.eligible == 2
    assert cov_c4_before.received == 0
    assert cov_c4_before.coverage == 0.0

    # Ingest recommendation for 1 student
    await db[col.RECOMMENDATIONS].insert_one({
        "recommendation_id": "rec_001",
        "pid": pids[0],
        "week_index": 1,
        "candidates": [{
            "intervention_type": "counsellor_outreach",
            "suitability_score": 0.85,
            "rationale": "High anxiety",
            "rank": 1,
        }],
        "status": "pending",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    })

    cov_c4_after = await compute_stage_coverage(db, "c4", "CS101", 1, eligible_pids=eligible)
    assert cov_c4_after.eligible == 2
    assert cov_c4_after.received == 1
    assert cov_c4_after.coverage == 0.5


# ── Part E: State Machine Progression & End-to-End Pipeline Run ──────────────

@pytest.mark.asyncio
async def test_stage_progression_complete_lifecycle(throwaway_pipeline_db):
    """
    Simulates a full lifecycle:
    1. Run starts pending -> lms_aggregation runs -> complete
    2. C1 & C2 become ready
    3. C1 & C2 receive data -> complete
    4. C3 becomes ready -> receives data -> complete
    5. C4 becomes ready -> receives data -> complete
    6. Overall run completes with audit logs
    """
    _, _, db = throwaway_pipeline_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(now)

    pids = [f"STU_{i:04d}1234" for i in range(5)]
    await setup_test_course_and_consent(db, "SE402", pids, week_index=1, now=now)

    # Register mock lms_aggregation handler
    async def mock_agg(db, course_id, week_index):
        return {"status": "complete", "note": "5 behavior records created"}
    register_stage_handler("lms_aggregation", mock_agg)

    run = await create_pipeline_run(db, "SE402", 1, week_end=now - timedelta(hours=2), now=now)
    assert run["status"] == "pending"

    # Step 1: Advance pending run
    run = await advance_pipeline_run(db, run, now=now)
    assert run["status"] == "running"
    assert run["stages"]["lms_aggregation"]["status"] == "complete"
    assert run["stages"]["c1"]["status"] == "ready"
    assert run["stages"]["c2"]["status"] == "ready"
    assert run["stages"]["c3"]["status"] == "waiting"

    # Verify PIPELINE_RUN_STARTED audit log
    audit_start = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.PIPELINE_RUN_STARTED})
    assert audit_start is not None
    assert audit_start["target_id"] == run["run_id"]

    # Step 2: Feed data for C1 and C2 (100% coverage: all 5 students)
    for p in pids:
        await db[col.AFFECTIVE_WEEKLY].insert_one({
            "pid": p, "course_id": "SE402", "week_index": 1,
            "emotion_scores": {"exam_anxiety": 0.4}, "stress_label": "low",
            "confidence": 0.9, "message_count": 2, "top_drivers": [],
            "schema_version": 1, "ingested_at": now, "source_version": "1.0",
        })
        await db[col.ENGAGEMENT_TRAJECTORIES].insert_one({
            "pid": p, "course_id": "SE402", "week_index": 1,
            "trajectory_label": "stable", "confidence": 0.95,
            "contributing_indicators": ["consistent_logins"],
            "schema_version": 1, "ingested_at": now, "source_version": "1.0",
        })

    run = await advance_pipeline_run(db, run, now=now)
    assert run["stages"]["c1"]["status"] == "complete"
    assert run["stages"]["c2"]["status"] == "complete"
    assert run["stages"]["c3"]["status"] == "ready"
    assert run["stages"]["c4"]["status"] == "waiting"

    # Step 3: Feed data for C3 (all 5 students, but only 1 at HIGH risk)
    for i, p in enumerate(pids):
        tier = "high" if i == 0 else "low"
        await db[col.RISK_ASSESSMENTS].insert_one({
            "pid": p, "course_id": "SE402", "week_index": 1,
            "risk_score": 0.85 if i == 0 else 0.2, "risk_tier": tier,
            "modality_contributions": {"affective": 0.4, "behavioral": 0.4, "academic": 0.2},
            "top_drivers": [], "schema_version": 1, "ingested_at": now, "source_version": "1.0",
        })

    run = await advance_pipeline_run(db, run, now=now)
    assert run["stages"]["c3"]["status"] == "complete"
    assert run["stages"]["c4"]["status"] == "ready"

    # Step 4: Feed recommendation for the 1 high-risk student
    await db[col.RECOMMENDATIONS].insert_one({
        "recommendation_id": "rec_final_01", "pid": pids[0], "week_index": 1,
        "candidates": [{
            "intervention_type": "academic_tutoring",
            "suitability_score": 0.9,
            "rationale": "High disengagement score",
            "rank": 1,
        }],
        "status": "pending", "schema_version": 1, "ingested_at": now, "source_version": "1.0",
    })

    run = await advance_pipeline_run(db, run, now=now)
    assert run["stages"]["c4"]["status"] == "complete"
    assert run["status"] == "complete"
    assert run["ended_at"] is not None

    # Verify PIPELINE_RUN_FINISHED audit log
    audit_end = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.PIPELINE_RUN_FINISHED})
    assert audit_end is not None
    assert audit_end["target_id"] == run["run_id"]
    assert audit_end["details"]["final_status"] == "complete"


# ── Part F: Timeout and Partial Completion ───────────────────────────────────

@pytest.mark.asyncio
async def test_stage_timeout_transitions_to_partial(throwaway_pipeline_db):
    """Verifies that an uncompleted stage times out after PIPELINE_STAGE_TIMEOUT_HOURS."""
    _, _, db = throwaway_pipeline_db
    t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(t0)

    pids = [f"STU_{i:04d}5678" for i in range(10)]
    await setup_test_course_and_consent(db, "NET201", pids, week_index=1, now=t0)

    async def mock_agg(db, course_id, week_index):
        return {"status": "complete"}
    register_stage_handler("lms_aggregation", mock_agg)

    run = await create_pipeline_run(db, "NET201", 1, week_end=t0 - timedelta(hours=2), now=t0)
    run = await advance_pipeline_run(db, run, now=t0)

    assert run["stages"]["c1"]["status"] == "ready"

    # Ingest 2 records out of 10 for C1 (20% coverage < 90%)
    for p in pids[:2]:
        await db[col.AFFECTIVE_WEEKLY].insert_one({
            "pid": p, "course_id": "NET201", "week_index": 1,
            "emotion_scores": {"exam_anxiety": 0.5}, "stress_label": "med",
            "confidence": 0.8, "message_count": 1, "top_drivers": [],
            "schema_version": 1, "ingested_at": t0, "source_version": "1.0",
        })

    # Advance immediately: becomes 'receiving'
    run = await advance_pipeline_run(db, run, now=t0)
    assert run["stages"]["c1"]["status"] == "receiving"

    # Advance time past 24-hour timeout (t0 + 25 hours)
    t1 = t0 + timedelta(hours=25)
    set_clock(t1)

    run = await advance_pipeline_run(db, run, now=t1)
    # C1 received partial records -> status becomes 'partial'
    assert run["stages"]["c1"]["status"] == "partial"
    # C2 received 0 records -> status becomes 'timed_out'
    assert run["stages"]["c2"]["status"] == "timed_out"

    # Both C1 and C2 are in terminal states -> C3 can now proceed to 'ready'
    assert run["stages"]["c3"]["status"] == "ready"


# ── Part G: Webhook HMAC Signing & Dispatch ───────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_hmac_signing_and_dispatch():
    """Verifies HMAC-SHA256 signature formatting and dispatch handling."""
    secret = "test_signing_secret_12345"
    ts = "2026-10-15T12:00:00+00:00"
    body = '{"event":"stage_ready"}'

    sig = sign_payload(secret, ts, body)
    assert sig.startswith("sha256=")
    assert len(sig) == 7 + 64

    # Test dispatch when no webhook is configured -> clean no-op
    res = await dispatch_stage_ready_webhook("c1", "CS101", 1, "run_001")
    assert res["notified"] is False
    assert res["attempts"] == 0


# ── Part H: Orchestrator Tick and Dry-Run ──────────────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_tick_and_dry_run(throwaway_pipeline_db):
    """Verifies that run_pipeline_tick executes end-to-end and dry-run skips writes."""
    _, _, db = throwaway_pipeline_db
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    set_clock(now)

    pids = ["STU_9999aaaa", "STU_8888bbbb"]
    await setup_test_course_and_consent(db, "BIO301", pids, week_index=1, now=now)
    await db[col.COURSE_WEEKS].update_one(
        {"course_id": "BIO301", "week_index": 1},
        {"$set": {"end_date": now - timedelta(hours=3)}}
    )

    # 1. Dry run tick
    dry_report = await run_pipeline_tick(db, now=now, dry_run=True)
    assert dry_report["status"] == "success"
    assert dry_report["dry_run"] is True
    assert dry_report["runs_created"] == 1
    # Check that database has NO pipeline_runs documents
    count = await db[col.PIPELINE_RUNS].count_documents({})
    assert count == 0

    # 2. Live tick
    live_report = await run_pipeline_tick(db, now=now, dry_run=False)
    assert live_report["status"] == "success"
    assert live_report["dry_run"] is False
    assert live_report["runs_created"] == 1

    # Check that run was created and advanced
    run_doc = await db[col.PIPELINE_RUNS].find_one({"course_id": "BIO301", "week_index": 1})
    assert run_doc is not None
    assert run_doc["status"] in ("running", "complete")
