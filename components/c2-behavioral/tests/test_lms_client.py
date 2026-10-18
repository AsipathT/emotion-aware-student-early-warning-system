"""
Unit tests for LMS API client using httpx.MockTransport.
"""

import json
import httpx
import pytest

from service.lms_client import LmsClient
from service.schemas import BehaviorRecord, TrajectoryRecord, build_envelope


def _sample_behavior_dict(pid: str = "STU_11112222", week: int = 0) -> dict:
    return {
        "pid": pid,
        "course_id": "CS101",
        "week_index": week,
        "login_count": 2,
        "session_minutes": 25.0,
        "clicks": 15,
        "video_play_count": 0,
        "video_pause_count": 0,
        "video_rewind_count": 0,
        "video_skip_count": 0,
        "video_completion_pct": 0.0,
        "submissions_count": 1,
        "avg_submission_delay_hours": 0.0,
    }


def test_fetch_behavior_pagination_and_auth():
    """Pagination over 2 pages is merged and header X-Component-Key is sent."""
    sent_headers = {}
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_headers["X-Component-Key"] = request.headers.get("X-Component-Key")
        page = request.url.params.get("page", "1")
        requested_pages.append(page)

        if page == "1":
            data = [_sample_behavior_dict(f"STU_{i:08x}", 0) for i in range(500)]
            body = {"data": data, "page": 1, "page_size": 500, "total": 650}
        else:
            data = [_sample_behavior_dict(f"STU_{i:08x}", 0) for i in range(500, 650)]
            body = {"data": data, "page": 2, "page_size": 500, "total": 650}

        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = LmsClient(
        base_url="http://test-lms",
        component_key="secret-api-key-999",
        transport=transport,
    )

    records = client.fetch_behavior(course_id="CS101")
    assert len(records) == 650
    assert sent_headers.get("X-Component-Key") == "secret-api-key-999"
    assert requested_pages == ["1", "2"]


def test_post_trajectory_dry_run_param_and_auth():
    """Ingest called with dry_run=true query parameter."""
    sent_query = {}
    sent_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent_query["dry_run"] = request.url.params.get("dry_run")
        sent_headers["X-Component-Key"] = request.headers.get("X-Component-Key")
        return httpx.Response(
            200,
            json={
                "run_id": "run-001",
                "schema_version": "1.0",
                "dry_run": True,
                "received": 1,
                "accepted": 1,
                "rejected": 0,
                "created": 1,
                "updated": 0,
                "rejected_records": [],
            },
        )

    transport = httpx.MockTransport(handler)
    client = LmsClient(
        base_url="http://test-lms",
        component_key="my-key-123",
        transport=transport,
    )

    env = build_envelope(
        [
            TrajectoryRecord(
                pid="STU_11112222",
                course_id="CS101",
                week_index=4,
                trajectory_label="stable",
                confidence=0.9,
                contributing_indicators=[],
            )
        ]
    )

    res = client.post_trajectory(env, dry_run=True)
    assert sent_query.get("dry_run") == "true"
    assert sent_headers.get("X-Component-Key") == "my-key-123"
    assert res["accepted"] == 1


def test_non_200_raises_without_leaking_key():
    """Non-200 raises RuntimeError whose message never contains the component key."""
    key = "super-secret-component-key-xyz"

    def handler(request: httpx.Request) -> httpx.Response:
        # Simulate server error message that mentions the key
        return httpx.Response(500, text=f"Auth error with {key} occurred")

    transport = httpx.MockTransport(handler)
    client = LmsClient(
        base_url="http://test-lms",
        component_key=key,
        transport=transport,
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.fetch_behavior(course_id="CS101")

    err_msg = str(exc_info.value)
    assert "HTTP 500" in err_msg
    assert key not in err_msg


def test_split_and_merge_1500_records():
    """1500 records are split into 2 POST requests and counts are merged."""
    post_counts = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        chunk_len = len(payload.get("data", []))
        post_counts.append(chunk_len)
        return httpx.Response(
            200,
            json={
                "run_id": "run-batch",
                "schema_version": "1.0",
                "dry_run": True,
                "received": chunk_len,
                "accepted": chunk_len,
                "rejected": 0,
                "created": chunk_len,
                "updated": 0,
                "rejected_records": [],
            },
        )

    transport = httpx.MockTransport(handler)
    client = LmsClient(
        base_url="http://test-lms",
        component_key="secret",
        transport=transport,
    )

    recs = [
        TrajectoryRecord(
            pid=f"STU_{i:08x}",
            course_id="CS101",
            week_index=4,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=[],
        )
        for i in range(1500)
    ]
    env = build_envelope(recs)

    merged = client.post_trajectory(env, dry_run=True)
    assert post_counts == [1000, 500]
    assert merged["received"] == 1500
    assert merged["accepted"] == 1500
