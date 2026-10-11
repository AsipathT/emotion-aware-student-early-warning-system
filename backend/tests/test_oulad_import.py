"""
backend/tests/test_oulad_import.py

Feature 26: Test Suite for OULAD Ingestion, Validation, and Rollback.
Runs strictly against real MongoDB Atlas throwaway databases (never mongomock).
Cleans up and drops test databases unconditionally in teardown.
"""

import copy
import csv
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio
from pymongo import MongoClient

# Setup sys.path
for p in ["/", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

from app.core.config import settings
from app.core.database import create_mongo_client
from app.core.privacy import is_valid_pid
from app.db import collections as col
from app.importers.oulad import mappings
from app.importers.oulad.engine import OuladImportEngine
from scripts.setup_db import setup_database
from scripts.verify_integrity import verify_integrity

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "oulad"


@pytest_asyncio.fixture
async def throwaway_oulad_db():
    """
    Provisions a unique isolated test database (lms_test_oulad_<hex>),
    applies migrations and validators, yields (uri, db_name), and
    drops the database in teardown.
    """
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_oulad_{uuid.uuid4().hex[:8]}"
    async_client = create_mongo_client(uri)
    db = async_client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        async_client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    # Initialize collections and validators
    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    yield uri, test_db_name

    # Unconditional teardown
    try:
        await async_client.drop_database(test_db_name)
    finally:
        async_client.close()


# ── Test 1: Full Import Creates Valid Records in All Target Collections ───────

@pytest.mark.asyncio
async def test_full_import_creates_valid_records(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(
        data_dir=FIXTURES_DIR,
        mongo_uri=uri,
        db_name=db_name,
        dry_run=False,
    )
    stats = engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        assert stats["total_records_processed"] > 0
        assert db[col.COURSES].count_documents({"source": "oulad"}) == 2
        assert db[col.COURSE_WEEKS].count_documents({"source": "oulad"}) > 0
        assert db[col.IDENTITY_VAULT].count_documents({"source": "oulad"}) == 4
        assert db[col.ENROLMENTS].count_documents({"source": "oulad"}) == 5
        assert db[col.ASSIGNMENTS].count_documents({"source": "oulad"}) == 6
        assert db[col.SUBMISSIONS].count_documents({"source": "oulad"}) == 9
        assert db[col.GRADES].count_documents({"source": "oulad"}) == 9
        assert db[col.ACTIVITY_EVENTS].count_documents({"source": "oulad"}) == 7
        assert db[col.INGESTION_RUNS].count_documents({"component": "oulad_importer"}) == 1
        assert db[col.AUDIT_LOGS].count_documents({"actor_id": "system:oulad_importer"}) == 1
    finally:
        sync_client.close()


# ── Test 2: Second Run Adds Nothing (Idempotent) ──────────────────────────────

@pytest.mark.asyncio
async def test_second_run_adds_nothing_idempotent(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine1 = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine1.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        count_courses_1 = db[col.COURSES].count_documents({})
        count_events_1 = db[col.ACTIVITY_EVENTS].count_documents({})
        count_grades_1 = db[col.GRADES].count_documents({})

        # Second import execution
        engine2 = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
        stats2 = engine2.run_import()

        assert db[col.COURSES].count_documents({}) == count_courses_1
        assert db[col.ACTIVITY_EVENTS].count_documents({}) == count_events_1
        assert db[col.GRADES].count_documents({}) == count_grades_1
        assert stats2["records_skipped_duplicate"] > 0
    finally:
        sync_client.close()


# ── Test 3: No Raw Student ID or Demographics in Analytics ────────────────────

@pytest.mark.asyncio
async def test_no_raw_student_id_or_demographics_in_analytics(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        raw_ids = ["11391", "28400", "31604", "45678"]
        excluded_fields = mappings.EXCLUDED_DEMOGRAPHIC_FIELDS

        for collection_name in [col.ACTIVITY_EVENTS, col.GRADES, col.SUBMISSIONS, col.ENROLMENTS]:
            docs = list(db[collection_name].find({}))
            assert len(docs) > 0
            for doc in docs:
                # 1. pid must be valid Feature 5 format
                assert is_valid_pid(doc["pid"])
                # 2. No raw student IDs present
                assert doc["pid"] not in raw_ids
                assert "id_student" not in doc
                assert "student_id" not in doc
                # 3. No excluded demographic fields present
                for field in excluded_fields:
                    assert field not in doc

        # Identity vault contains placeholder metadata
        vault_docs = list(db[col.IDENTITY_VAULT].find({}))
        for v in vault_docs:
            assert is_valid_pid(v["pid"])
            assert v["name"] == "OULAD Student"
            assert v["is_imported"] is True
            assert v["student_id"].startswith("OULAD_")
    finally:
        sync_client.close()


# ── Test 4: Negative Days Map to Week 0 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_negative_days_map_to_week_zero(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        # Student 11391 had day -10 in studentVle.csv
        pid = mappings.oulad_pid(11391)
        # Anchor for 2013J is 2013-10-01 00:00:00 UTC
        # Day -10 timestamp is 2013-09-21 00:00:00 UTC
        pre_event = db[col.ACTIVITY_EVENTS].find_one({"pid": pid, "timestamp": datetime(2013, 9, 21, 0, 0, tzinfo=timezone.utc)})
        assert pre_event is not None
        assert pre_event["week_index"] == 0
    finally:
        sync_client.close()


# ── Test 5: Blank Dates Handled Explicitly ────────────────────────────────────

@pytest.mark.asyncio
async def test_blank_dates_handled(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        # Assessment 1758 had blank date (Exam) -> due date set to presentation end (268 days)
        exam = db[col.ASSIGNMENTS].find_one({"assignment_id": "1758"})
        assert exam is not None
        assert exam["due_date"] == datetime(2014, 6, 26, 0, 0, tzinfo=timezone.utc)
        assert exam["week_index"] == 38

        # Student 11391 in AAA_2013J had blank date_unregistration -> enrolment_end is None
        pid = mappings.oulad_pid(11391)
        enr = db[col.ENROLMENTS].find_one({"pid": pid, "course_id": "AAA_2013J"})
        assert enr is not None
        assert enr["enrolment_end"] is None
        assert enr["unregistration_week"] is None
        assert enr["status"] == "completed"
    finally:
        sync_client.close()


# ── Test 6: Multiple Assessments in One Week Do Not Overwrite ─────────────────

@pytest.mark.asyncio
async def test_multiple_assessments_in_one_week_do_not_overwrite(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        # Student 11391 in BBB_2014B took both 1760 and 1761 in week 2
        pid = mappings.oulad_pid(11391)
        grades = list(db[col.GRADES].find({"pid": pid, "course_id": "BBB_2014B"}))
        assert len(grades) == 2

        assessment_ids = {g["assessment_id"] for g in grades}
        assert "1760" in assessment_ids
        assert "1761" in assessment_ids

        # Both occurred in week 2
        for g in grades:
            assert g["week_index"] == 2
    finally:
        sync_client.close()


# ── Test 7: Withdrawn Status and Unregistration Week Correct ──────────────────

@pytest.mark.asyncio
async def test_withdrawn_status_and_unregistration_week(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        # Student 45678 withdrew on day 45 in BBB_2014B
        pid = mappings.oulad_pid(45678)
        enr = db[col.ENROLMENTS].find_one({"pid": pid, "course_id": "BBB_2014B"})
        assert enr is not None
        assert enr["status"] == "withdrawn"
        assert enr["final_result"] == "Withdrawn"
        assert enr["unregistration_week"] == 6  # 45 // 7 = 6
        assert enr["enrolment_end"] == datetime(2014, 3, 18, 0, 0, tzinfo=timezone.utc)
    finally:
        sync_client.close()


# ── Test 8: Works with Tiny Chunk Size (Multiple Chunks) ──────────────────────

@pytest.mark.asyncio
async def test_works_with_tiny_chunk_size(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    # Chunk size 2 forces multiple chunks during studentVle streaming
    engine = OuladImportEngine(
        data_dir=FIXTURES_DIR,
        mongo_uri=uri,
        db_name=db_name,
        chunk_size=2,
    )
    stats = engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        assert stats["collections_written"][col.ACTIVITY_EVENTS] == 7
        assert db[col.ACTIVITY_EVENTS].count_documents({}) == 7
    finally:
        sync_client.close()


# ── Test 9: Dry Run Writes Nothing ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_writes_nothing(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(
        data_dir=FIXTURES_DIR,
        mongo_uri=uri,
        db_name=db_name,
        dry_run=True,
    )
    stats = engine.run_import()

    assert stats["dry_run"] is True
    assert stats["total_records_processed"] > 0

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        for collection_name in [col.COURSES, col.IDENTITY_VAULT, col.ENROLMENTS, col.ACTIVITY_EVENTS, col.GRADES]:
            assert db[collection_name].count_documents({}) == 0
    finally:
        sync_client.close()


# ── Test 10: Rollback Removes Imported Records and Preserves Others ───────────

@pytest.mark.asyncio
async def test_rollback_removes_imported_preserves_others(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    # 1. Perform import
    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        # Plant manual non-OULAD documents
        db[col.COURSES].insert_one({
            "_id": "course_CS999",
            "course_id": "CS999",
            "title": "Manual Course",
            "source": "manual",
            "schema_version": 1,
            "ingested_at": datetime.now(timezone.utc),
            "source_version": "1.0",
        })
        db[col.IDENTITY_VAULT].insert_one({
            "_id": "vault_STU_11112222",
            "pid": "STU_11112222",
            "student_id": "MANUAL_01",
            "name": "Manual Student",
            "email": "manual@test.invalid",
            "source": "manual",
            "schema_version": 1,
            "ingested_at": datetime.now(timezone.utc),
            "source_version": "1.0",
        })

        # 2. Run Rollback
        deleted_counts = engine.rollback()
        assert deleted_counts[col.COURSES] == 2
        assert deleted_counts[col.IDENTITY_VAULT] == 4

        # 3. Verify OULAD records deleted
        assert db[col.COURSES].count_documents({"source": "oulad"}) == 0
        assert db[col.IDENTITY_VAULT].count_documents({"source": "oulad"}) == 0
        assert db[col.ACTIVITY_EVENTS].count_documents({}) == 0

        # 4. Verify manual records untouched
        assert db[col.COURSES].count_documents({"source": "manual"}) == 1
        assert db[col.IDENTITY_VAULT].count_documents({"source": "manual"}) == 1

        # 5. Audit logs preserved and logged DATA_ROLLBACK
        assert db[col.AUDIT_LOGS].count_documents({"action": "DATA_ROLLBACK"}) == 1
    finally:
        sync_client.close()


# ── Test 11: Bad Row is Reported and Skipped ──────────────────────────────────

@pytest.mark.asyncio
async def test_bad_row_reported_and_skipped(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    # Create temporary fixtures directory with a malformed course row (negative length)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for f in FIXTURES_DIR.glob("*.csv"):
            shutil.copy(f, tmp_path / f.name)

        # Append bad row to courses.csv with negative presentation length
        with open(tmp_path / "courses.csv", "a", encoding="utf-8") as f:
            f.write("BAD,2014J,-99\n")

        engine = OuladImportEngine(data_dir=tmp_path, mongo_uri=uri, db_name=db_name)
        stats = engine.run_import()

        # Engine reports rejection without raising or crashing
        assert len(stats["rejected_records"]) > 0
        assert any("CourseStorage" in r for r in stats["rejected_records"])


# ── Test 12: verify_integrity.py Passes After Import ──────────────────────────

@pytest.mark.asyncio
async def test_verify_integrity_passes_after_import(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    engine = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name)
    engine.run_import()

    # Run verify_integrity check
    async_client = create_mongo_client(uri)
    db = async_client[db_name]
    try:
        is_healthy, violations = await verify_integrity(db)
        assert is_healthy is True
        assert len(violations) == 0
    finally:
        async_client.close()


# ── Test 13: Deterministic Sampling ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_deterministic_sampling(throwaway_oulad_db):
    uri, db_name = throwaway_oulad_db

    # Run 1: sample 2 with seed 777
    engine1 = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name, sample_size=2, seed=777)
    stats1 = engine1.run_import()

    sync_client = MongoClient(uri, tz_aware=True)
    db = sync_client[db_name]
    try:
        pids1 = sorted(list(db[col.IDENTITY_VAULT].distinct("pid")))
        assert len(pids1) == 2

        # Clean and run 2: sample 2 with seed 777
        engine1.rollback()
        engine2 = OuladImportEngine(data_dir=FIXTURES_DIR, mongo_uri=uri, db_name=db_name, sample_size=2, seed=777)
        stats2 = engine2.run_import()

        pids2 = sorted(list(db[col.IDENTITY_VAULT].distinct("pid")))
        assert pids1 == pids2
    finally:
        sync_client.close()
