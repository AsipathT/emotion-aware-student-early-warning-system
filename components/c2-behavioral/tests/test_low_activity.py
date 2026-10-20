"""
Unit tests for the low_activity_vs_history indicator and its integration with inference.
"""

import pandas as pd
import pytest

from src.indicators import low_activity_vs_history
from src.inference import predict_trajectory
from tests.test_pipeline import make_dummy_bundle


def test_low_activity_vs_history_positive():
    """[100, 100, 100, 100, 20, 20, 20] -> True (recent 20 <= 0.25 * prior 100 = 25)."""
    clicks = [100.0, 100.0, 100.0, 100.0, 20.0, 20.0, 20.0]
    assert low_activity_vs_history(clicks) is True


def test_low_activity_vs_history_flat():
    """[100]*7 -> False (recent 100 > 0.25 * prior 100 = 25)."""
    clicks = [100.0] * 7
    assert low_activity_vs_history(clicks) is False


def test_low_activity_vs_history_moderate_drop():
    """[100, 100, 100, 100, 40, 40, 40] -> False (40 > 25)."""
    clicks = [100.0, 100.0, 100.0, 100.0, 40.0, 40.0, 40.0]
    assert low_activity_vs_history(clicks) is False


def test_low_activity_vs_history_insufficient_weeks():
    """5 weeks -> False (requires >= 6 weeks)."""
    clicks = [100.0, 100.0, 20.0, 20.0, 20.0]
    assert low_activity_vs_history(clicks) is False


def test_low_activity_vs_history_prior_zero():
    """Prior all zero -> False (prior <= 0)."""
    clicks = [0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0]
    assert low_activity_vs_history(clicks) is False


def test_inference_low_activity_replaces_steady_activity():
    """
    History clicks [130, 110, 100, 90, 80, 20, 18, 12, 12, 12] weeks 0..9:
    returned indicators contain 'low_activity_vs_own_history' and not 'steady_activity'.
    """
    clicks = [130.0, 110.0, 100.0, 90.0, 80.0, 20.0, 18.0, 12.0, 12.0, 12.0]
    history = pd.DataFrame(
        {
            "week": list(range(len(clicks))),
            "clicks": clicks,
            "submissions_count": [0.0] * len(clicks),
            "avg_delay_hours": [0.0] * len(clicks),
        }
    )
    bundle = make_dummy_bundle()
    res = predict_trajectory(history, bundle=bundle)

    assert res is not None
    assert "low_activity_vs_own_history" in res["contributing_indicators"]
    assert "steady_activity" not in res["contributing_indicators"]
