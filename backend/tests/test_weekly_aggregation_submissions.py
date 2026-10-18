"""
backend/tests/test_weekly_aggregation_submissions.py

Pure unit tests for weekly aggregation submissions filtering and metric calculations.
Requires no database connection and no conftest fixtures.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.jobs.weekly_aggregation import select_submissions_for_week
from app.services.week_index import compute_week_index


def test_select_submissions_by_week_and_delay_computation():
    """
    Test with 4 submissions in weeks 1, 1, 2, 3 with delays 2, 4, 10, -6.
    Verifies:
      - week 1 -> count 2 and average delay 3.0
      - week 2 -> count 1 and average delay 10.0
      - week 4 -> count 0 and default average 0.0 stays in the caller
    """
    submissions: List[Dict[str, Any]] = [
        {"submission_id": "s1", "week_index": 1, "delay_hours": 2.0},
        {"submission_id": "s2", "week_index": 1, "delay_hours": 4.0},
        {"submission_id": "s3", "week_index": 2, "delay_hours": 10.0},
        {"submission_id": "s4", "week_index": 3, "delay_hours": -6.0},
    ]

    def week_of(sub: Dict[str, Any]):
        return sub.get("week_index")

    def aggregate_metrics(selected_subs: List[Dict[str, Any]]) -> tuple[int, float]:
        count = 0
        delay_hours_sum = 0.0
        for sub in selected_subs:
            sub_delay = sub.get("delay_hours")
            count += 1
            if sub_delay is not None:
                try:
                    delay_hours_sum += float(sub_delay)
                except (ValueError, TypeError):
                    pass
        avg_delay = round(delay_hours_sum / count, 2) if count > 0 else 0.0
        return count, avg_delay

    # Week 1 -> count 2 and average 3.0
    w1_subs = select_submissions_for_week(submissions, 1, week_of)
    w1_count, w1_avg = aggregate_metrics(w1_subs)
    assert w1_count == 2
    assert w1_avg == 3.0
    assert [s["submission_id"] for s in w1_subs] == ["s1", "s2"]

    # Week 2 -> count 1
    w2_subs = select_submissions_for_week(submissions, 2, week_of)
    w2_count, w2_avg = aggregate_metrics(w2_subs)
    assert w2_count == 1
    assert w2_avg == 10.0
    assert [s["submission_id"] for s in w2_subs] == ["s3"]

    # Week 4 -> count 0 (default 0.0 stays in caller)
    w4_subs = select_submissions_for_week(submissions, 4, week_of)
    w4_count, w4_avg = aggregate_metrics(w4_subs)
    assert w4_count == 0
    assert w4_avg == 0.0
    assert w4_subs == []


def test_submission_with_undetermined_week_is_excluded():
    """
    Submissions whose week cannot be determined (week_of returns None)
    must be excluded from the filtered list.
    """
    submissions: List[Dict[str, Any]] = [
        {"submission_id": "valid_w1", "week_index": 1, "delay_hours": 2.5},
        {"submission_id": "no_week_field", "delay_hours": 5.0},
        {"submission_id": "none_week", "week_index": None, "delay_hours": 1.0},
    ]

    def week_of(sub: Dict[str, Any]):
        return sub.get("week_index")

    # Filter for week 1
    w1_subs = select_submissions_for_week(submissions, 1, week_of)
    assert len(w1_subs) == 1
    assert w1_subs[0]["submission_id"] == "valid_w1"

    # Filter for week 0
    w0_subs = select_submissions_for_week(submissions, 0, week_of)
    assert len(w0_subs) == 0

    # Filter with a week_of that always returns None
    assert select_submissions_for_week(submissions, 1, lambda s: None) == []


def test_empty_list_returns_empty_list():
    """Empty list of submissions must return an empty list."""
    def week_of(sub: Dict[str, Any]):
        return sub.get("week_index")

    assert select_submissions_for_week([], 1, week_of) == []
    assert select_submissions_for_week([], 0, week_of) == []
    assert select_submissions_for_week([], -1, week_of) == []


def test_select_submissions_with_compute_week_index():
    """
    Integration test using compute_week_index to verify submitted_at timestamp
    resolution to academic week indices.
    """
    course_created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    submissions = [
        {
            "submission_id": "sub_w0",
            "submitted_at": datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc),
            "delay_hours": 1.5,
        },
        {
            "submission_id": "sub_w1",
            "submitted_at": datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
            "delay_hours": 5.0,
        },
        {
            "submission_id": "sub_undetermined",
            "submitted_at": None,
            "delay_hours": 0.0,
        },
    ]

    def week_of(sub: Dict[str, Any]):
        ts = sub.get("submitted_at")
        if ts is None:
            return None
        return compute_week_index(ts, None, course_created_at)

    w0 = select_submissions_for_week(submissions, 0, week_of)
    assert len(w0) == 1
    assert w0[0]["submission_id"] == "sub_w0"

    w1 = select_submissions_for_week(submissions, 1, week_of)
    assert len(w1) == 1
    assert w1[0]["submission_id"] == "sub_w1"

    w2 = select_submissions_for_week(submissions, 2, week_of)
    assert len(w2) == 0
