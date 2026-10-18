"""
Integration tests for Component 2 FastAPI application and endpoints.
"""

import time
from fastapi.testclient import TestClient
import pytest

from service.app import create_app
from tests.test_pipeline import make_dummy_bundle, make_rec


def test_health_endpoint():
    """GET /health returns status ok with loaded model metadata."""
    bundle = make_dummy_bundle()
    app = create_app(bundle)
    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == "test"


def test_classify_happy_path():
    """POST /classify returns envelope with source 'c2' and classification stats."""
    bundle = make_dummy_bundle()
    app = create_app(bundle)
    client = TestClient(app)

    recs = [make_rec("STU_12345678", "CS101", w, clicks=20) for w in range(8)]
    payload = {
        "records": [r.model_dump() for r in recs],
        "week": None,
    }

    resp = client.post("/classify", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    assert "envelope" in body
    assert "stats" in body
    assert body["envelope"]["source"] == "c2"
    assert body["envelope"]["schema_version"] == "1.0"
    assert len(body["envelope"]["data"]) == 1
    assert body["stats"]["classified"] == 1


def test_classify_invalid_pid_422():
    """POST /classify with invalid pid returns HTTP 422 Unprocessable Entity."""
    bundle = make_dummy_bundle()
    app = create_app(bundle)
    client = TestClient(app)

    bad_record = make_rec("STU_12345678", "CS101", 0).model_dump()
    bad_record["pid"] = "INVALID_PID_FORMAT"

    payload = {
        "records": [bad_record],
        "week": None,
    }

    resp = client.post("/classify", json=payload)
    assert resp.status_code == 422


def test_classify_missing_model_503(monkeypatch, tmp_path):
    """create_app(None) with a missing model file returns HTTP 503 on /classify."""
    non_existent = tmp_path / "missing_model.joblib"
    monkeypatch.setenv("C2_MODEL_PATH", str(non_existent))

    app = create_app(None)
    client = TestClient(app)

    # Health check shows model_loaded is False
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["model_loaded"] is False

    # /classify returns 503
    payload = {"records": [], "week": None}
    resp = client.post("/classify", json=payload)
    assert resp.status_code == 503


def test_classify_latency_check():
    """Classify 100 students x 12 weeks in one /classify call; elapsed < 2.0s."""
    bundle = make_dummy_bundle()
    app = create_app(bundle)
    client = TestClient(app)

    records = []
    for s in range(100):
        pid = f"STU_{s:08x}"
        for w in range(12):
            records.append(make_rec(pid, "CS101", w, clicks=20).model_dump())

    payload = {
        "records": records,
        "week": None,
    }

    t0 = time.perf_counter()
    resp = client.post("/classify", json=payload)
    elapsed = time.perf_counter() - t0

    print(f"\n[LATENCY CHECK] 100 students x 12 weeks classified in {elapsed:.4f} seconds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stats"]["classified"] == 100
    assert elapsed < 2.0, f"Latency {elapsed:.4f}s exceeded 2.0s limit"
