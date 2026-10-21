"""
tests/test_extend_demo_weeks.py

Unit tests for pure helper functions in scripts/extend_demo_weeks.py.
Verifies week range parsing, clicks generation, pattern coverage,
document builders, missing key filtering, and live safety validations.
Does NOT import pymongo, pandas, or connect to any database.
"""

from datetime import datetime, timezone
from pathlib import Path
import random
import pytest

from scripts.extend_demo_weeks import (
    PATTERNS,
    assign_student_pattern,
    build_behavior_doc,
    build_risk_doc,
    get_mongo_db,
    next_clicks,
    parse_week_range,
    select_missing,
    validate_live_args,
)


def test_parse_week_range_valid():
    """Verify standard range parsing [10, 14] returns weeks 10 through 14."""
    weeks = parse_week_range(10, 14)
    assert weeks == [10, 11, 12, 13, 14]
    assert parse_week_range(5, 5) == [5]


def test_parse_week_range_invalid():
    """Verify inverted, negative, or invalid types raise ValueError."""
    with pytest.raises(ValueError, match="Invalid week range"):
        parse_week_range(14, 10)

    with pytest.raises(ValueError, match="negative"):
        parse_week_range(-1, 5)

    with pytest.raises(ValueError, match="negative"):
        parse_week_range(5, -2)

    with pytest.raises(ValueError, match="integers"):
        parse_week_range("10", 14)  # type: ignore


def test_next_clicks_never_negative_and_deterministic():
    """Verify clicks are always non-negative integers and deterministic for fixed seed."""
    rng1 = random.Random(2026)
    c1 = next_clicks([50, 40, 30], rng1, pattern="continue_decline")
    assert isinstance(c1, int)
    assert c1 >= 0

    # Determinism test
    rng_a = random.Random(42)
    rng_b = random.Random(42)
    clicks_a = [next_clicks([20], rng_a, pattern="flat") for _ in range(10)]
    clicks_b = [next_clicks([20], rng_b, pattern="flat") for _ in range(10)]
    assert clicks_a == clicks_b

    # Negative history edge case
    rng_neg = random.Random(99)
    assert next_clicks([-10], rng_neg, pattern="continue_decline") == 0


def test_every_pattern_covered():
    """Verify each of the 4 patterns behaves according to specification."""
    rng = random.Random(1234)

    # 1. continue_decline: x0.8
    res_decline = next_clicks([100], rng, pattern="continue_decline")
    assert res_decline == 80

    # 2. recover: x1.3, capped at 120
    res_recover = next_clicks([50], rng, pattern="recover")
    assert res_recover == 65

    res_recover_cap = next_clicks([100], rng, pattern="recover")
    assert res_recover_cap == 120  # 100 * 1.3 = 130 -> capped at 120

    # 3. flat: x(0.9 - 1.1)
    res_flat = next_clicks([100], rng, pattern="flat")
    assert 90 <= res_flat <= 110

    # 4. volatile: alternates x0.5 and x1.8 based on step
    res_vol_step0 = next_clicks([100], rng, pattern="volatile", step=0)
    assert res_vol_step0 == 50  # 100 * 0.5 = 50

    res_vol_step1 = next_clicks([50], rng, pattern="volatile", step=1)
    assert res_vol_step1 == 90  # 50 * 1.8 = 90


def test_assign_student_pattern_deterministic():
    """Verify deterministic assignment of a valid pattern to each student PID."""
    p1 = assign_student_pattern(2026, "STU_1001")
    p2 = assign_student_pattern(2026, "STU_1001")
    assert p1 == p2
    assert p1 in PATTERNS


def test_build_behavior_doc_keys_source_and_id():
    """Verify build_behavior_doc preserves keys, scales telemetry, and formats _id."""
    prev_doc = {
        "_id": "STU_001_CS101_9",
        "pid": "STU_001",
        "course_id": "CS101",
        "week_index": 9,
        "clicks": 100,
        "login_count": 10,
        "session_minutes": 150.0,
        "video_play_count": 6,
        "video_pause_count": 4,
        "video_completion_pct": 80.0,
        "submissions_count": 2,
        "avg_submission_delay_hours": 1.5,
        "schema_version": 1,
        "source_version": "1.0",
        "custom_metadata_tag": "keep_me",
    }

    new_doc = build_behavior_doc(prev_doc, week_index=10, clicks=50)

    # _id convention: f"{pid}_{course_id}_{week_index}"
    assert new_doc["_id"] == "STU_001_CS101_10"
    assert new_doc["week_index"] == 10
    assert new_doc["clicks"] == 50
    assert new_doc["source"] == "synthetic"
    assert isinstance(new_doc["ingested_at"], datetime)
    assert new_doc["ingested_at"].tzinfo == timezone.utc

    # Scaling ratio is 50/100 = 0.5
    assert new_doc["login_count"] == 5
    assert new_doc["session_minutes"] == 75.0
    assert new_doc["video_play_count"] == 3
    assert new_doc["video_pause_count"] == 2
    assert new_doc["video_completion_pct"] == 40.0

    # Fixed fields unchanged
    assert new_doc["submissions_count"] == 2
    assert new_doc["avg_submission_delay_hours"] == 1.5
    assert new_doc["custom_metadata_tag"] == "keep_me"


def test_build_behavior_doc_clamping():
    """Verify video_completion_pct is clamped to 100.0 on large click expansions."""
    prev_doc = {
        "_id": "STU_002_CS101_9",
        "pid": "STU_002",
        "course_id": "CS101",
        "week_index": 9,
        "clicks": 20,
        "video_completion_pct": 75.0,
    }
    # 4x increase in clicks
    new_doc = build_behavior_doc(prev_doc, week_index=10, clicks=80)
    assert new_doc["video_completion_pct"] == 100.0


def test_build_risk_doc_modality_sum_and_fields():
    """Verify build_risk_doc preserves risk metrics and keeps modality sum at 1.0."""
    prev_risk = {
        "_id": "STU_001_CS101_9",
        "pid": "STU_001",
        "course_id": "CS101",
        "week_index": 9,
        "risk_score": 0.65,
        "risk_tier": "high",
        "modality_contributions": {
            "affective": 0.45,
            "behavioral": 0.30,
            "academic": 0.25,
        },
        "top_drivers": ["declining_clicks", "late_submissions"],
        "schema_version": 1,
        "source_version": "1.0",
    }

    new_risk = build_risk_doc(prev_risk, week_index=10)

    assert new_risk["_id"] == "STU_001_CS101_10"
    assert new_risk["week_index"] == 10
    assert new_risk["source"] == "synthetic"
    assert new_risk["risk_score"] == 0.65
    assert new_risk["risk_tier"] == "high"
    assert new_risk["top_drivers"] == ["declining_clicks", "late_submissions"]

    mods = new_risk["modality_contributions"]
    assert sum(mods.values()) == pytest.approx(1.0, abs=1e-5)


def test_select_missing():
    """Verify existing documents are skipped and only missing candidates are returned."""
    existing_keys = {
        ("STU_1", "CS101", 10),
        ("STU_2", "CS101", 10),
    }

    candidates = [
        {"pid": "STU_1", "course_id": "CS101", "week_index": 10, "data": "old"},
        {"pid": "STU_2", "course_id": "CS101", "week_index": 10, "data": "old"},
        {"pid": "STU_3", "course_id": "CS101", "week_index": 10, "data": "new"},
        {"pid": "STU_1", "course_id": "CS101", "week_index": 11, "data": "new"},
    ]

    missing = select_missing(existing_keys, candidates)
    assert len(missing) == 2
    missing_ids = {(m["pid"], m["week_index"]) for m in missing}
    assert missing_ids == {("STU_3", 10), ("STU_1", 11)}


def test_live_mode_refuses_when_confirm_course_differs():
    """Verify safety guard raises ValueError on live write without matching confirmation."""
    # Live mode with mismatched or missing confirmation must fail
    with pytest.raises(ValueError, match="Live write requires --confirm-course matching"):
        validate_live_args(course_id="CS101", confirm_course=None, dry_run=False)

    with pytest.raises(ValueError, match="Live write requires --confirm-course matching"):
        validate_live_args(course_id="CS101", confirm_course="SE4020", dry_run=False)

    # Live mode with exact match succeeds without exception
    validate_live_args(course_id="CS101", confirm_course="CS101", dry_run=False)

    # Dry-run mode does not require confirmation
    validate_live_args(course_id="CS101", confirm_course=None, dry_run=True)


def test_get_mongo_db_requires_mongo_uri_and_no_srv(monkeypatch):
    """Verify get_mongo_db exits when MONGO_URI is unset and source has no hard-coded srv string."""
    # 1. Check get_mongo_db exits when MONGO_URI is unset
    monkeypatch.delenv("MONGO_URI", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        get_mongo_db()
    assert "MONGO_URI environment variable is not set" in str(exc_info.value)

    # 2. Check that the script source code contains no "mongodb+srv" or "mongodb://"
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "extend_demo_weeks.py"
    script_text = script_path.read_text(encoding="utf-8").lower()
    assert "mongodb+srv" not in script_text
    assert "mongodb://" not in script_text

