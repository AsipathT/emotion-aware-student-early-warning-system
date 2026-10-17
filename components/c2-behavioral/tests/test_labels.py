"""
Unit tests for window statistics calculation and trajectory labeling logic.
"""

import numpy as np
import pandas as pd
import pytest

from src.labels import compute_labels, label_from_stats, window_stats


def test_window_stats_and_labels():
    # 1. Flat engagement -> stable
    e_flat = np.full(7, 3.0)
    slope_flat, resid_sd_flat = window_stats(e_flat)
    assert np.isclose(slope_flat, 0.0)
    assert np.isclose(resid_sd_flat, 0.0)
    assert label_from_stats(slope_flat, resid_sd_flat) == "stable"

    # 2. Linear declining -> declining (slope -1.0)
    e_dec = np.array([6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0])
    slope_dec, resid_sd_dec = window_stats(e_dec)
    assert np.isclose(slope_dec, -1.0)
    assert np.isclose(resid_sd_dec, 0.0)
    assert label_from_stats(slope_dec, resid_sd_dec) == "declining"

    # 3. Linear improving -> improving (slope +1.0)
    e_imp = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    slope_imp, resid_sd_imp = window_stats(e_imp)
    assert np.isclose(slope_imp, 1.0)
    assert np.isclose(resid_sd_imp, 0.0)
    assert label_from_stats(slope_imp, resid_sd_imp) == "improving"

    # 4. Alternating values -> volatile (resid_sd >= 1.0 and abs(slope) < 0.10)
    e_vol = np.array([0.0, 3.0, 0.0, 3.0, 0.0, 3.0, 0.0])
    slope_vol, resid_sd_vol = window_stats(e_vol)
    assert np.isclose(slope_vol, 0.0)
    assert resid_sd_vol >= 1.0
    assert label_from_stats(slope_vol, resid_sd_vol) == "volatile"


def test_compute_labels_dormant_windows():
    # Dense frame with one student, clicks all 0 for weeks 0..8 (9 weeks total)
    weeks = list(range(9))
    dense = pd.DataFrame({
        "code_module": ["AAA"] * 9,
        "code_presentation": ["2013J"] * 9,
        "id_student": [1001] * 9,
        "week": weeks,
        "clicks": [0] * 9,
        "active_days": [0] * 9,
        "submissions_count": [0] * 9,
        "avg_delay_hours": [0.0] * 9,
        "final_result": ["Withdrawn"] * 9,
    })

    labels = compute_labels(dense)
    # 9 rows -> 3 windows at weeks 3, 4, 5
    assert len(labels) == 3
    assert list(labels["week"]) == [3, 4, 5]
    assert all(labels["dormant"] == True)
    assert all(labels["label"] == "dormant")


def test_compute_labels_stable_windows_and_week_filtering():
    # Dense frame with one student, clicks = [10]*9 (weeks 0..8)
    weeks = list(range(9))
    dense = pd.DataFrame({
        "code_module": ["BBB"] * 9,
        "code_presentation": ["2014B"] * 9,
        "id_student": [2002] * 9,
        "week": weeks,
        "clicks": [10] * 9,
        "active_days": [2] * 9,
        "submissions_count": [0] * 9,
        "avg_delay_hours": [0.0] * 9,
        "final_result": ["Pass"] * 9,
    })

    labels = compute_labels(dense)
    # Windows must exist at weeks 3, 4, 5 and not at week 2 or 6
    assert len(labels) == 3
    assert list(labels["week"]) == [3, 4, 5]
    assert all(labels["label"] == "stable")
    assert all(labels["dormant"] == False)
    assert 2 not in labels["week"].values
    assert 6 not in labels["week"].values


def test_compute_labels_window_span_boundary():
    # 1. Student with 6 rows (weeks 0..5): exactly 0 windows (7 needed)
    dense_6 = pd.DataFrame({
        "code_module": ["CCC"] * 6,
        "code_presentation": ["2014J"] * 6,
        "id_student": [3003] * 6,
        "week": list(range(6)),
        "clicks": [5] * 6,
        "active_days": [1] * 6,
        "submissions_count": [0] * 6,
        "avg_delay_hours": [0.0] * 6,
        "final_result": ["Fail"] * 6,
    })
    labels_6 = compute_labels(dense_6)
    assert len(labels_6) == 0

    # 2. Student with 7 rows (weeks 0..6): exactly 1 window at centre week 3
    dense_7 = pd.DataFrame({
        "code_module": ["CCC"] * 7,
        "code_presentation": ["2014J"] * 7,
        "id_student": [3003] * 7,
        "week": list(range(7)),
        "clicks": [5] * 7,
        "active_days": [1] * 7,
        "submissions_count": [0] * 7,
        "avg_delay_hours": [0.0] * 7,
        "final_result": ["Fail"] * 7,
    })
    labels_7 = compute_labels(dense_7)
    assert len(labels_7) == 1
    assert labels_7.iloc[0]["week"] == 3
    assert labels_7.iloc[0]["label"] == "stable"
