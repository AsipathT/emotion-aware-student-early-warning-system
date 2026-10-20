"""
backend/tests/test_event_week.py

Pure unit tests for resolve_event_week service.
Uses no database connection, no conftest fixtures, and runs with monkeypatched get_week_index.
"""

import asyncio
from datetime import datetime, timezone

from app.services import event_week
from app.services.event_week import resolve_event_week


def test_resolve_event_week_success(monkeypatch):
    """Returns the fake value when course_id is set (e.g. 4) and passes arguments through."""
    recorded_calls = []

    async def fake_get_week_index(db, course_id: str, ts=None):
        recorded_calls.append((db, course_id, ts))
        return 4

    monkeypatch.setattr(event_week, "get_week_index", fake_get_week_index)

    dummy_db = object()
    test_ts = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
    result = asyncio.run(resolve_event_week(dummy_db, "CS101", test_ts, fallback=1))

    assert result == 4
    assert len(recorded_calls) == 1
    assert recorded_calls[0] == (dummy_db, "CS101", test_ts)


def test_resolve_event_week_falsy_course_id(monkeypatch):
    """Returns fallback when course_id is None or empty, without invoking get_week_index."""
    call_count = 0

    async def fake_get_week_index(db, course_id: str, ts=None):
        nonlocal call_count
        call_count += 1
        return 4

    monkeypatch.setattr(event_week, "get_week_index", fake_get_week_index)

    dummy_db = object()
    test_ts = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)

    # course_id is None -> returns fallback immediately
    res_none = asyncio.run(resolve_event_week(dummy_db, None, test_ts, fallback=1))
    assert res_none == 1

    # course_id is empty string -> returns fallback immediately
    res_empty = asyncio.run(resolve_event_week(dummy_db, "", test_ts, fallback=2))
    assert res_empty == 2

    # Verify get_week_index was never called
    assert call_count == 0


def test_resolve_event_week_exception_returns_fallback(monkeypatch):
    """Returns fallback when get_week_index raises an exception."""
    async def fake_get_week_index(db, course_id: str, ts=None):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(event_week, "get_week_index", fake_get_week_index)

    dummy_db = object()
    test_ts = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
    result = asyncio.run(resolve_event_week(dummy_db, "CS101", test_ts, fallback=1))

    assert result == 1


def test_resolve_event_week_passes_ts_and_converts_course_id_str(monkeypatch):
    """Passes ts and str(course_id) through to get_week_index."""
    recorded_calls = []

    async def fake_get_week_index(db, course_id: str, ts=None):
        recorded_calls.append((db, course_id, ts))
        return 6

    monkeypatch.setattr(event_week, "get_week_index", fake_get_week_index)

    dummy_db = object()
    test_ts = datetime(2026, 4, 1, 14, 30, tzinfo=timezone.utc)
    result = asyncio.run(resolve_event_week(dummy_db, "course_xyz", test_ts, fallback=0))

    assert result == 6
    assert len(recorded_calls) == 1
    assert recorded_calls[0] == (dummy_db, "course_xyz", test_ts)
