"""
Unit tests for the batch classification pipeline.
"""

import numpy as np
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from service.pipeline import classify_records
from service.schemas import BehaviorRecord
from src.deploy_features import DEPLOY_FEATURES


def make_dummy_bundle():
    """Builds a lightweight in-memory bundle for unit testing."""
    import pandas as pd
    rng = np.random.RandomState(42)
    X = pd.DataFrame(rng.randn(200, len(DEPLOY_FEATURES)), columns=DEPLOY_FEATURES)
    y = rng.choice(["declining", "improving", "stable", "volatile"], size=200)
    clf = HistGradientBoostingClassifier(
        max_iter=10,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    clf.fit(X, y)
    return {
        "model": clf,
        "features": DEPLOY_FEATURES,
        "version": "test",
    }


def make_rec(
    pid: str,
    course_id: str,
    week_index: int,
    clicks: int = 10,
    subs: int = 0,
    delay: float = 0.0,
) -> BehaviorRecord:
    return BehaviorRecord(
        pid=pid,
        course_id=course_id,
        week_index=week_index,
        login_count=1,
        session_minutes=10.0,
        clicks=clicks,
        video_play_count=0,
        video_pause_count=0,
        video_rewind_count=0,
        video_skip_count=0,
        video_completion_pct=0.0,
        submissions_count=subs,
        avg_submission_delay_hours=delay,
    )


def test_pipeline_standard_weeks_0_to_7():
    """(1) group with weeks 0..7 -> 1 classified record with week_index 7."""
    bundle = make_dummy_bundle()
    recs = [make_rec("STU_11112222", "AAA", w, clicks=20) for w in range(8)]
    results, stats = classify_records(recs, bundle)

    assert stats["classified"] == 1
    assert len(results) == 1
    assert results[0].week_index == 7
    assert results[0].pid == "STU_11112222"


def test_pipeline_cold_start():
    """(2) group with only week 2 -> skipped cold_start."""
    bundle = make_dummy_bundle()
    recs = [make_rec("STU_11112222", "AAA", 2, clicks=20)]
    results, stats = classify_records(recs, bundle)

    assert stats["classified"] == 0
    assert stats["skipped"]["cold_start"] == 1
    assert len(results) == 0


def test_pipeline_missing_middle_weeks():
    """(3) missing middle weeks are zero-filled (history contiguous, no exception)."""
    bundle = make_dummy_bundle()
    # Weeks 0 and 5 only (weeks 1, 2, 3, 4 are missing and should be zero-filled)
    recs = [
        make_rec("STU_11112222", "AAA", 0, clicks=50),
        make_rec("STU_11112222", "AAA", 5, clicks=30),
    ]
    results, stats = classify_records(recs, bundle)

    assert stats["classified"] == 1
    assert len(results) == 1
    assert results[0].week_index == 5


def test_pipeline_dormant_never_active():
    """(4) 10 weeks of zero clicks -> label 'declining', indicators ['never_active'], confidence 0.86."""
    bundle = make_dummy_bundle()
    recs = [make_rec("STU_11112222", "AAA", w, clicks=0) for w in range(10)]
    results, stats = classify_records(recs, bundle)

    assert stats["classified"] == 1
    assert results[0].trajectory_label == "declining"
    assert results[0].confidence == pytest.approx(0.86)
    assert results[0].contributing_indicators == ["never_active"]


def test_pipeline_error_isolation(monkeypatch):
    """(5) two students, one raising an exception inside predict -> the other still classified, error count 1."""
    bundle = make_dummy_bundle()
    recs_stu1 = [make_rec("STU_11111111", "AAA", w, clicks=20) for w in range(6)]
    recs_stu2 = [make_rec("STU_22222222", "AAA", w, clicks=20) for w in range(6)]

    # Monkeypatch predict_trajectory to fail only for student 1
    from src import inference

    orig_predict = inference.predict_trajectory

    def mock_predict(history, bndl):
        # Student 1 triggers exception
        if history["clicks"].iloc[0] == 999:
            raise RuntimeError("Simulated model inference crash")
        return orig_predict(history, bndl)

    monkeypatch.setattr("service.pipeline.predict_trajectory", mock_predict)

    # Set student 1 click to 999
    recs_stu1[0] = make_rec("STU_11111111", "AAA", 0, clicks=999)

    results, stats = classify_records(recs_stu1 + recs_stu2, bundle)

    assert stats["classified"] == 1
    assert stats["skipped"]["error"] == 1
    assert len(results) == 1
    assert results[0].pid == "STU_22222222"


def test_pipeline_target_week_respected():
    """(6) target_week respected."""
    bundle = make_dummy_bundle()
    recs = [make_rec("STU_11112222", "AAA", w, clicks=20) for w in range(8)]

    # Target week 4 (must classify at week 4)
    results, stats = classify_records(recs, bundle, target_week=4)
    assert stats["classified"] == 1
    assert results[0].week_index == 4

    # Target week 12 (not in records -> skipped no_row_for_week)
    results_missing, stats_missing = classify_records(recs, bundle, target_week=12)
    assert stats_missing["classified"] == 0
    assert stats_missing["skipped"]["no_row_for_week"] == 1
