"""
tests/test_export_samples.py

Unit tests for helper functions used in export_samples.py:
  - make_pid formatting and determinism
  - build_dormant_records schema validation
  - sample_stratified correctness
  - compute_confidence_quantiles statistics
"""

import re
import numpy as np
import pandas as pd
import pytest

from scripts.export_samples import (
    build_dormant_records,
    compute_confidence_quantiles,
    make_pid,
    sample_stratified,
)
from service.schemas import TrajectoryRecord
from src.config import DORMANT_RULE_CONFIDENCE

PID_REGEX = re.compile(r"^STU_[0-9a-f]{8}$")


def test_make_pid_format_and_determinism():
    """make_pid must match ^STU_[0-9a-f]{8}$ and produce identical output for identical inputs."""
    pid1 = make_pid("AAA", "2013J", 12345)
    pid2 = make_pid("AAA", "2013J", 12345)
    assert pid1 == pid2
    assert PID_REGEX.match(pid1) is not None

    pid3 = make_pid("AAA", "2013J", 12346)
    assert pid1 != pid3
    assert PID_REGEX.match(pid3) is not None


def test_make_pid_string_and_int_id():
    """make_pid handles string and int student IDs cleanly."""
    pid_int = make_pid("BBB", "2014B", 98765)
    pid_str = make_pid("BBB", "2014B", "98765")
    assert pid_int == pid_str
    assert PID_REGEX.match(pid_int) is not None


def test_build_dormant_records():
    """build_dormant_records returns exactly 5 valid TrajectoryRecords with declining label."""
    records = build_dormant_records()
    assert len(records) == 5

    for rec in records:
        assert isinstance(rec, TrajectoryRecord)
        assert PID_REGEX.match(rec.pid) is not None
        assert rec.trajectory_label == "declining"
        assert rec.confidence == pytest.approx(DORMANT_RULE_CONFIDENCE, abs=1e-5)
        assert len(rec.contributing_indicators) > 0
        assert all(ind in ["no_activity_7w", "never_active"] for ind in rec.contributing_indicators)


def test_sample_stratified():
    """sample_stratified samples up to n_per_class per label deterministically."""
    data = {
        "id": range(100),
        "predicted_label": (
            ["declining"] * 30 + ["improving"] * 25 + ["stable"] * 25 + ["volatile"] * 20
        ),
        "val": range(100),
    }
    df = pd.DataFrame(data)

    sampled = sample_stratified(df, label_col="predicted_label", n_per_class=10, random_state=42)
    assert len(sampled) == 40
    counts = sampled["predicted_label"].value_counts().to_dict()
    assert counts == {"declining": 10, "improving": 10, "stable": 10, "volatile": 10}

    # Verify reproducibility with fixed seed
    sampled2 = sample_stratified(df, label_col="predicted_label", n_per_class=10, random_state=42)
    assert sampled.equals(sampled2)


def test_compute_confidence_quantiles():
    """compute_confidence_quantiles accurately calculates percentiles and aggregates."""
    labels = np.array(["stable"] * 50 + ["declining"] * 50)
    confs = np.linspace(0.4, 0.9, 100)

    quantiles = compute_confidence_quantiles(labels, confs)
    assert "stable" in quantiles
    assert "declining" in quantiles
    assert "overall" in quantiles

    for key, stats in quantiles.items():
        assert stats["min"] <= stats["p05"]
        assert stats["p05"] <= stats["p25"]
        assert stats["p25"] <= stats["p50"]
        assert stats["p50"] <= stats["p75"]
        assert stats["p75"] <= stats["p95"]
        assert stats["p95"] <= stats["p99"]
        assert stats["p99"] <= stats["max"]
        assert stats["min"] <= stats["mean"] <= stats["max"]
