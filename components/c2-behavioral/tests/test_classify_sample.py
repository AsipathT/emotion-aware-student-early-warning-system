"""
Unit and integration tests for the classify sample payload builder.
Verifies schema compliance, record counts, and execution via FastAPI TestClient.
"""

from fastapi.testclient import TestClient
import pytest

from scripts.make_classify_sample import build_classify_sample
from service.app import create_app
from service.schemas import BehaviorRecord
from tests.test_pipeline import make_dummy_bundle


def test_classify_sample_structure_and_validation():
    """Verify that build_classify_sample produces 120 valid records for 12 students at week 9."""
    sample = build_classify_sample()

    assert "records" in sample
    assert "week" in sample
    assert sample["week"] == 9

    records = sample["records"]
    assert len(records) == 120

    # Validate every record with Pydantic schema
    validated_records = [BehaviorRecord.model_validate(r) for r in records]
    assert len(validated_records) == 120

    # Exactly 12 distinct PIDs
    pids = {r.pid for r in validated_records}
    assert len(pids) == 12

    # Every student has exactly weeks 0..9 in course DEMO_C2
    expected_weeks = set(range(10))
    for pid in pids:
        student_weeks = {r.week_index for r in validated_records if r.pid == pid}
        assert student_weeks == expected_weeks
        student_courses = {r.course_id for r in validated_records if r.pid == pid}
        assert student_courses == {"DEMO_C2"}


def test_classify_sample_post_endpoint():
    """Verify that POST /classify accepts the sample payload and returns 12 trajectories."""
    sample = build_classify_sample()
    bundle = make_dummy_bundle()
    app = create_app(bundle)
    client = TestClient(app)

    resp = client.post("/classify", json=sample)
    assert resp.status_code == 200
    body = resp.json()

    assert "envelope" in body
    assert "stats" in body
    assert body["envelope"]["source"] == "c2"
    assert body["envelope"]["schema_version"] == "1.0"

    data = body["envelope"]["data"]
    assert len(data) == 12
    assert body["stats"]["classified"] == 12
    assert body["stats"]["received_groups"] == 12
