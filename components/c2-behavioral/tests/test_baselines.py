"""
Unit tests for baseline models (MajorityBaseline and rule_predict heuristic).
"""

import numpy as np
import pytest

from src.baselines import MajorityBaseline, rule_predict


def test_rule_predict_thresholds():
    """rule_predict: ratio 0.5 -> declining; 1.5 -> improving; 1.0 -> stable;
    prior_mean 0 -> stable; never returns 'volatile'."""
    assert rule_predict(0.5, 1.0) == "declining"
    assert rule_predict(1.5, 1.0) == "improving"
    assert rule_predict(1.0, 1.0) == "stable"
    assert rule_predict(50.0, 0.0) == "stable"

    # Batch evaluation
    clicks = [5.0, 15.0, 10.0, 100.0, 0.0, 999.0]
    priors = [10.0, 10.0, 10.0, 0.0, 10.0, 1.0]
    preds = rule_predict(clicks, priors)

    expected = ["declining", "improving", "stable", "stable", "declining", "improving"]
    assert list(preds) == expected
    assert "volatile" not in preds


def test_majority_baseline():
    """MajorityBaseline predicts the most frequent class."""
    y = ["improving", "stable", "stable", "declining", "stable"]
    baseline = MajorityBaseline()
    baseline.fit(y)

    preds_int = baseline.predict(4)
    assert len(preds_int) == 4
    assert np.all(preds_int == "stable")

    preds_arr = baseline.predict(y)
    assert len(preds_arr) == len(y)
    assert np.all(preds_arr == "stable")
