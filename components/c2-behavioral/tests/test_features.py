"""
Unit tests for feature engineering routines (causal features and static features).
Uses purely hand-made mock DataFrames with no disk or OULAD dependencies.
"""

import numpy as np
import pandas as pd
import pytest

from src.features import build_causal_features, build_static_features


def _make_dummy_frames(
    clicks: list,
    weeks: list,
    label_weeks: list,
    mod: str = "AAA",
    pres: str = "2013J",
    sid: int = 1001,
):
    """Helper to create minimal valid dense and labels DataFrames."""
    n = len(clicks)
    dense = pd.DataFrame(
        {
            "code_module": [mod] * n,
            "code_presentation": [pres] * n,
            "id_student": [sid] * n,
            "week": weeks,
            "clicks": clicks,
            "active_days": [1 if c > 0 else 0 for c in clicks],
            "submissions_count": [0] * n,
            "avg_delay_hours": [0.0] * n,
            "final_result": ["Pass"] * n,
        }
    )

    n_lbl = len(label_weeks)
    labels = pd.DataFrame(
        {
            "code_module": [mod] * n_lbl,
            "code_presentation": [pres] * n_lbl,
            "id_student": [sid] * n_lbl,
            "week": label_weeks,
            "slope": [0.0] * n_lbl,
            "resid_sd": [0.1] * n_lbl,
            "dormant": [False] * n_lbl,
            "label": ["stable"] * n_lbl,
            "final_result": ["Pass"] * n_lbl,
        }
    )
    return dense, labels


def test_clicks_lags_at_t():
    """clicks [0,10,100,1000,10,5,3,2,1] weeks 0..8 for one student:
    at t=5 e_lag0 == log1p(5), e_lag5 == log1p(0); at t=3 e_lag4 and e_lag5 are NaN."""
    clicks = [0, 10, 100, 1000, 10, 5, 3, 2, 1]
    weeks = list(range(9))
    label_weeks = [3, 5]

    dense, labels = _make_dummy_frames(clicks, weeks, label_weeks)
    feat = build_causal_features(dense, labels)

    # Check at t=5
    row_t5 = feat[feat["week"] == 5].iloc[0]
    assert np.isclose(row_t5["e_lag0"], np.log1p(5))
    assert np.isclose(row_t5["e_lag5"], np.log1p(0))

    # Check at t=3
    row_t3 = feat[feat["week"] == 3].iloc[0]
    assert np.isnan(row_t3["e_lag4"])
    assert np.isnan(row_t3["e_lag5"])
    assert np.isclose(row_t3["e_lag0"], np.log1p(1000))
    assert np.isclose(row_t3["e_lag3"], np.log1p(0))


def test_no_future_leak():
    """NO FUTURE LEAK: change clicks at weeks > t to huge values;
    every feature row for centre t must be identical before/after."""
    clicks_orig = [10, 20, 30, 40, 50, 60, 70, 80]
    clicks_future_changed = [10, 20, 30, 40, 50, 999999, 888888, 777777]
    weeks = list(range(8))
    # Evaluating centre t=4 (uses weeks 0..4)
    label_weeks = [4]

    dense1, labels1 = _make_dummy_frames(clicks_orig, weeks, label_weeks)
    dense2, labels2 = _make_dummy_frames(clicks_future_changed, weeks, label_weeks)

    feat1 = build_causal_features(dense1, labels1)
    feat2 = build_causal_features(dense2, labels2)

    pd.testing.assert_frame_equal(feat1, feat2)


def test_e_slope4_exact_value():
    """e_slope4 for clicks making e_lag3..e_lag0 = [0,1,2,3]
    compute expected = sum([-1.5,-.5,.5,1.5]*[0,1,2,3])/5 = 1.0."""
    e_target = [0.0, 1.0, 2.0, 3.0]
    clicks = [float(np.expm1(val)) for val in e_target]
    weeks = [0, 1, 2, 3]
    label_weeks = [3]

    dense, labels = _make_dummy_frames(clicks, weeks, label_weeks)
    feat = build_causal_features(dense, labels)

    expected_slope = (
        -1.5 * e_target[0] - 0.5 * e_target[1] + 0.5 * e_target[2] + 1.5 * e_target[3]
    ) / 5.0
    assert expected_slope == pytest.approx(1.0)
    assert feat.iloc[0]["e_slope4"] == pytest.approx(1.0)


def test_zero_run():
    """zero_run: weeks clicks [5,5,0,0,0,7...] at t=4 gives 3."""
    clicks = [5, 5, 0, 0, 0, 7]
    weeks = list(range(6))
    label_weeks = [4]

    dense, labels = _make_dummy_frames(clicks, weeks, label_weeks)
    feat = build_causal_features(dense, labels)

    assert feat.iloc[0]["zero_run"] == 3
