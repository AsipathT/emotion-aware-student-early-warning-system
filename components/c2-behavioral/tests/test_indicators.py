"""
Unit tests for contributing indicator extraction rules.
"""

import numpy as np
from src.indicators import contributing_indicators


def test_indicators_slope():
    """slope -0.3 -> contains 'clicks_declining_trend'."""
    row = {
        "e_slope4": -0.3,
        "e_recent_diff": 0.0,
        "e_sd6": 0.2,
        "zero_weeks6": 0,
        "zero_run": 0,
        "delay_mean6": 0.0,
    }
    inds = contributing_indicators(row, "declining")
    assert "clicks_declining_trend" in inds


def test_indicators_all_neutral():
    """all-neutral row -> ['steady_activity']."""
    row = {
        "e_slope4": 0.0,
        "e_recent_diff": 0.0,
        "e_sd6": 0.2,
        "zero_weeks6": 0,
        "zero_run": 0,
        "delay_mean6": 0.0,
    }
    inds = contributing_indicators(row, "stable")
    assert inds == ["steady_activity"]


def test_indicators_delay():
    """delay_mean6 30 -> 'late_submissions'."""
    row = {
        "e_slope4": 0.0,
        "e_recent_diff": 0.0,
        "e_sd6": 0.2,
        "zero_weeks6": 0,
        "zero_run": 0,
        "delay_mean6": 30.0,
    }
    inds = contributing_indicators(row, "declining")
    assert "late_submissions" in inds


def test_indicators_nan_safety():
    """NaN values do not raise error and fall back gracefully."""
    row = {
        "e_slope4": np.nan,
        "e_recent_diff": np.nan,
        "e_sd6": np.nan,
        "zero_weeks6": np.nan,
        "zero_run": np.nan,
        "delay_mean6": np.nan,
    }
    inds = contributing_indicators(row, "stable")
    assert inds == ["steady_activity"]


def test_indicators_no_duplicates_and_max_len():
    """No duplicate indicators and maximum length is capped at 10."""
    row = {
        "e_slope4": -0.5,
        "e_recent_diff": -1.0,
        "e_sd6": 2.0,
        "zero_run": 3,
        "zero_weeks6": 4,
        "delay_mean6": 48.0,
    }
    inds = contributing_indicators(row, "declining")
    assert len(inds) <= 10
    assert len(inds) == len(set(inds))
