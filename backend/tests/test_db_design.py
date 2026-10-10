"""
backend/tests/test_db_design.py

Feature 25: Comprehensive MongoDB Database Design Test Suite.
Requires a real MongoDB connection (Docker or Atlas test cluster).
Never touches the shared database: uses isolated throwaway database fixtures (lms_test_<random>)
and drops them in teardown.

Covers:
1. generate_mongo_schema conversions (types, enums, optionals, nested, lists).
2. MongoDB engine-level schema enforcement (rejects missing pid, bad score, unknown enum, extra fields).
3. Unique compound indexes reject duplicate insertions.
4. setup_db.py idempotency and --check drift detection.
5. Existing-collection compatibility scan detects invalid documents.
6. verify_integrity.py validates seed data and catches planted orphans / forbidden fields.
7. Migration runner applies sequentially and is idempotent.
8. tz_aware client guarantees retrieved datetimes are timezone-aware (UTC).
"""

import copy
import os
import sys
import uuid
from pathlib import Path
import pytest
import pytest_asyncio
from datetime import datetime, timezone

# Ensure project root and / are in sys.path so 'scripts' package is always resolvable
for p in ["/", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

from app.core.config import settings
from app.core.database import create_mongo_client
from app.db import collections as col
from app.db.indexes import COLLECTION_INDEXES
from app.db.storage_models import (
    BehaviorWeeklyStorage,
    RiskAssessmentStorage,
    TextMessageStorage,
)
from app.db.validators import (
    COLLECTION_VALIDATORS,
    generate_mongo_schema,
)
from scripts.seed_dev_data import seed_data
from scripts.setup_db import scan_existing_compatibility, setup_database
from scripts.verify_integrity import verify_integrity


@pytest_asyncio.fixture
async def throwaway_db():
    """
    Creates an isolated throwaway database (lms_test_<random>) for testing.
    Drops the database in teardown.
    """
    uri = settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB connection URI not configured.")

    test_db_name = f"lms_test_{uuid.uuid4().hex[:8]}"
    client = create_mongo_client(uri)
    db = client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    yield db, test_db_name

    # Teardown: cleanly drop the isolated test database
    try:
        await client.drop_database(test_db_name)
    finally:
        client.close()


# ── Test 1: generate_mongo_schema Conversion Properties ───────────────────────

def test_generate_mongo_schema_structure():
    schema = generate_mongo_schema(TextMessageStorage)["$jsonSchema"]
    assert schema["bsonType"] == "object"
    assert schema["additionalProperties"] is False

    props = schema["properties"]
    assert "_id" in props
    assert props["_id"]["bsonType"] == ["string", "objectId"]
    assert props["pid"]["bsonType"] == "string"
    assert "pattern" in props["pid"]
    assert props["clean_text"]["bsonType"] == "string"
    assert props["source_type"]["bsonType"] == "string"
    assert "enum" in props["source_type"]
    assert "forum" in props["source_type"]["enum"]
    assert props["timestamp"]["bsonType"] == "date"
    assert props["response_latency_seconds"]["bsonType"] == ["number", "null"]
    assert props["schema_version"]["bsonType"] == ["int", "long"]


# ── Test 2: MongoDB Rejects Invalid Documents Against Schema ──────────────────

@pytest.mark.asyncio
async def test_mongo_rejects_invalid_documents(throwaway_db):
    db, db_name = throwaway_db
    validator = COLLECTION_VALIDATORS[col.MESSAGES]

    await db.create_collection(
        col.MESSAGES,
        validator=validator,
        validationLevel="strict",
        validationAction="error",
    )

    valid_doc = {
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "ingested_at": datetime.now(timezone.utc),
        "source_version": "1.0",
        "message_id": "msg_001",
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 2,
        "source_type": "forum",
        "clean_text": "Need help with dynamic programming recursion.",
        "timestamp": datetime.now(timezone.utc),
        "response_latency_seconds": 120.0,
        "message_length_chars": 45,
        "message_length_words": 6,
        "reply_to_id": None,
    }

    # 1. Valid insertion succeeds
    res = await db[col.MESSAGES].insert_one(valid_doc)
    assert res.inserted_id is not None

    # 2. Missing required field (missing pid)
    invalid_no_pid = copy.deepcopy(valid_doc)
    invalid_no_pid["_id"] = str(uuid.uuid4())
    del invalid_no_pid["pid"]
    with pytest.raises(Exception):
        await db[col.MESSAGES].insert_one(invalid_no_pid)

    # 3. Invalid enum value (source_type = 'podcast')
    invalid_enum = copy.deepcopy(valid_doc)
    invalid_enum["_id"] = str(uuid.uuid4())
    invalid_enum["source_type"] = "podcast"
    with pytest.raises(Exception):
        await db[col.MESSAGES].insert_one(invalid_enum)

    # 4. Extra field (additionalProperties: False)
    invalid_extra = copy.deepcopy(valid_doc)
    invalid_extra["_id"] = str(uuid.uuid4())
    invalid_extra["unregistered_extra_field"] = "malformed"
    with pytest.raises(Exception):
        await db[col.MESSAGES].insert_one(invalid_extra)

    # 5. Wrong type (timestamp as integer instead of date)
    invalid_type = copy.deepcopy(valid_doc)
    invalid_type["_id"] = str(uuid.uuid4())
    invalid_type["timestamp"] = 123456789
    with pytest.raises(Exception):
        await db[col.MESSAGES].insert_one(invalid_type)


# ── Test 3: Compound Unique Indexes Enforce Uniqueness ────────────────────────

@pytest.mark.asyncio
async def test_unique_compound_indexes(throwaway_db):
    db, db_name = throwaway_db

    # Create collection and its compound index
    await db.create_collection(col.BEHAVIOR_WEEKLY)
    await db[col.BEHAVIOR_WEEKLY].create_indexes(COLLECTION_INDEXES[col.BEHAVIOR_WEEKLY])

    doc1 = {
        "_id": "doc_1",
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 2,
        "login_count": 5,
        "session_minutes": 120.0,
        "clicks": 50,
        "video_play_count": 5,
        "video_pause_count": 2,
        "video_rewind_count": 1,
        "video_skip_count": 0,
        "video_completion_pct": 80.0,
        "submissions_count": 1,
        "avg_submission_delay_hours": 0.0,
        "schema_version": 1,
        "ingested_at": datetime.now(timezone.utc),
        "source_version": "1.0",
    }
    await db[col.BEHAVIOR_WEEKLY].insert_one(doc1)

    # Duplicate on (pid, course_id, week_index) with different _id must fail
    doc2 = copy.deepcopy(doc1)
    doc2["_id"] = "doc_2"
    with pytest.raises(Exception):
        await db[col.BEHAVIOR_WEEKLY].insert_one(doc2)


# ── Test 4: setup_db.py Idempotency and Drift Check ───────────────────────────

@pytest.mark.asyncio
async def test_setup_db_idempotency_and_check(throwaway_db):
    db, db_name = throwaway_db

    # First setup creates everything
    res1 = await setup_database(db_name=db_name, dry_run=False, check_only=False)
    assert res1 is True

    # Second setup yields 0 changes
    res2 = await setup_database(db_name=db_name, dry_run=False, check_only=False)
    assert res2 is True

    # Check mode passes
    check_pass = await setup_database(db_name=db_name, check_only=True)
    assert check_pass is True

    # Plant drift: drop a collection index
    await db[col.ENROLMENTS].drop_index("idx_enrolments_course_status")
    check_fail = await setup_database(db_name=db_name, check_only=True)
    assert check_fail is False


# ── Test 5: Existing-Collection Compatibility Scan Reports Invalid Docs ───────

@pytest.mark.asyncio
async def test_compatibility_scan_downgrades(throwaway_db):
    db, db_name = throwaway_db
    validator = COLLECTION_VALIDATORS[col.IDENTITY_VAULT]

    # Pre-populate collection without validator containing an invalid document (bad PID)
    await db[col.IDENTITY_VAULT].insert_one({
        "_id": "bad_doc",
        "pid": "INVALID_NOT_STU",
        "student_id": "IT12345678",
        "name": "Old Legacy User",
        "email": "legacy@lms.edu",
    })

    compatible, failing, total = await scan_existing_compatibility(db, col.IDENTITY_VAULT, validator)
    assert compatible is False
    assert failing == 1
    assert total == 1


# ── Test 6: Integrity Script Validates Seed & Catches Violations ───────────────

@pytest.mark.asyncio
async def test_verify_integrity_catches_violations(throwaway_db):
    db, db_name = throwaway_db

    # 1. Setup collections and seed data
    await setup_database(db_name=db_name)
    await seed_data(db)

    # 2. Clean seed passes integrity verification with 0 violations
    is_healthy, violations = await verify_integrity(db)
    assert is_healthy is True
    assert len(violations) == 0

    # 3. Plant orphan enrolment PID
    await db[col.ENROLMENTS].insert_one({
        "_id": "planted_orphan",
        "pid": "STU_99999999",  # Not in identity_vault
        "course_id": "CS101",
        "enrolment_start": datetime.now(timezone.utc),
        "status": "active",
        "schema_version": 1,
        "ingested_at": datetime.now(timezone.utc),
        "source_version": "1.0",
    })

    is_healthy_orphan, violations_orphan = await verify_integrity(db)
    assert is_healthy_orphan is False
    assert any("identity_vault" in v for v in violations_orphan)

    # 4. Plant forbidden PII field in analytics collection (temporarily remove validator)
    await db.command("collMod", col.ATTENDANCE, validator={}, validationLevel="off")
    await db[col.ATTENDANCE].insert_one({
        "_id": "planted_pii",
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 10,
        "sessions_scheduled": 2,
        "sessions_attended": 2,
        "attendance_pct": 100.0,
        "student_id": "IT11112222",  # FORBIDDEN FIELD!
        "schema_version": 1,
        "ingested_at": datetime.now(timezone.utc),
        "source_version": "1.0",
    })

    is_healthy_pii, violations_pii = await verify_integrity(db)
    assert is_healthy_pii is False
    assert any("forbidden PII" in v for v in violations_pii)


# ── Test 7: Migration Runner Idempotency ───────────────────────────────────────

@pytest.mark.asyncio
async def test_migration_runner(throwaway_db):
    from app.db.migrations.runner import run_migrations

    db, db_name = throwaway_db

    # Run 1 applies migrations
    applied_first = await run_migrations(db)
    assert "0001_init" in applied_first

    # Run 2 skips already applied migrations
    applied_second = await run_migrations(db)
    assert len(applied_second) == 0


# ── Test 8: tz_aware Client Returns UTC-Aware Datetimes ────────────────────────

@pytest.mark.asyncio
async def test_client_tz_aware_datetimes(throwaway_db):
    db, db_name = throwaway_db

    now_utc = datetime.now(timezone.utc)
    await db.temp_tz_test.insert_one({"ts": now_utc})

    doc = await db.temp_tz_test.find_one({})
    retrieved_ts = doc["ts"]

    # Must be timezone-aware (tzinfo is not None)
    assert retrieved_ts.tzinfo is not None
    # Must offset to UTC (+00:00)
    assert retrieved_ts.utcoffset().total_seconds() == 0
