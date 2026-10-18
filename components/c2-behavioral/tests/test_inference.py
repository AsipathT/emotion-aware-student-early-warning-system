"""
Unit tests for online trajectory inference pipeline.
"""

import pandas as pd
import pytest

from src.inference import predict_trajectory


def test_inference_cold_start():
    """3 weeks history -> None (too little history)."""
    history = pd.DataFrame(
        {
            "week": [0, 1, 2],
            "clicks": [10.0, 20.0, 15.0],
            "submissions_count": [0, 0, 0],
            "avg_delay_hours": [0.0, 0.0, 0.0],
        }
    )
    res = predict_trajectory(history, bundle=None)
    assert res is None


def test_inference_dormant_never_active():
    """10 weeks all zero clicks -> label 'declining', confidence 0.86, indicators ['never_active']."""
    history = pd.DataFrame(
        {
            "week": list(range(10)),
            "clicks": [0.0] * 10,
            "submissions_count": [0] * 10,
            "avg_delay_hours": [0.0] * 10,
        }
    )
    res = predict_trajectory(history, bundle=None)
    assert res is not None
    assert res["trajectory_label"] == "declining"
    assert res["confidence"] == pytest.approx(0.86)
    assert res["contributing_indicators"] == ["never_active"]


def test_inference_dormant_no_activity_7w():
    """clicks [5]+[0]*7 (8 weeks) -> ['no_activity_7w']."""
    history = pd.DataFrame(
        {
            "week": list(range(8)),
            "clicks": [5.0] + [0.0] * 7,
            "submissions_count": [0] * 8,
            "avg_delay_hours": [0.0] * 8,
        }
    )
    res = predict_trajectory(history, bundle=None)
    assert res is not None
    assert res["trajectory_label"] == "declining"
    assert res["confidence"] == pytest.approx(0.86)
    assert res["contributing_indicators"] == ["no_activity_7w"]


def test_inference_non_contiguous_weeks_raises():
    """Non-contiguous weeks -> ValueError."""
    history = pd.DataFrame(
        {
            "week": [0, 1, 3, 4],
            "clicks": [10.0, 10.0, 10.0, 10.0],
            "submissions_count": [0, 0, 0, 0],
            "avg_delay_hours": [0.0, 0.0, 0.0, 0.0],
        }
    )
    with pytest.raises(ValueError):
        predict_trajectory(history, bundle=None)
