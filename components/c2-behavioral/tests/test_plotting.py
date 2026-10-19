"""
tests/test_plotting.py

Tests for plot_trajectories in service/plotting.py.
Verifies multi-student grid rendering, all-zero clicks handling,
PNG output generation, and robust handling of trajectory label colors.
"""

from pathlib import Path
import pytest

from service.plotting import plot_trajectories
from service.schemas import BehaviorRecord, TrajectoryRecord


@pytest.fixture
def sample_behavior_and_trajectories():
    """Build hand-made records for 3 students across weeks 0..7, including one with all-zero clicks."""
    course_id = "DEMO_C2"
    pids = ["STU_1111aaaa", "STU_2222bbbb", "STU_3333cccc"]

    behavior_records = []
    # Student 1: Increasing clicks (improving)
    for w in range(8):
        behavior_records.append(
            BehaviorRecord(
                pid=pids[0],
                course_id=course_id,
                week_index=w,
                login_count=5 + w,
                session_minutes=60.0 + 10.0 * w,
                clicks=10 + 15 * w,
                video_play_count=2,
                video_pause_count=1,
                video_rewind_count=0,
                video_skip_count=0,
                video_completion_pct=80.0,
                submissions_count=1 if w > 0 else 0,
                avg_submission_delay_hours=-2.0,
            )
        )

    # Student 2: Decreasing clicks (declining)
    for w in range(8):
        behavior_records.append(
            BehaviorRecord(
                pid=pids[1],
                course_id=course_id,
                week_index=w,
                login_count=max(1, 8 - w),
                session_minutes=max(10.0, 120.0 - 15.0 * w),
                clicks=max(0, 100 - 14 * w),
                video_play_count=2,
                video_pause_count=1,
                video_rewind_count=1,
                video_skip_count=1,
                video_completion_pct=45.0,
                submissions_count=1 if w > 0 else 0,
                avg_submission_delay_hours=12.5,
            )
        )

    # Student 3: All-zero clicks (dormant / critical drop)
    for w in range(8):
        behavior_records.append(
            BehaviorRecord(
                pid=pids[2],
                course_id=course_id,
                week_index=w,
                login_count=0,
                session_minutes=0.0,
                clicks=0,
                video_play_count=0,
                video_pause_count=0,
                video_rewind_count=0,
                video_skip_count=0,
                video_completion_pct=0.0,
                submissions_count=0,
                avg_submission_delay_hours=0.0,
            )
        )

    trajectories = [
        TrajectoryRecord(
            pid=pids[0],
            course_id=course_id,
            week_index=7,
            trajectory_label="improving",
            confidence=0.88,
            contributing_indicators=["high_clicks_w7", "early_submission"],
        ),
        TrajectoryRecord(
            pid=pids[1],
            course_id=course_id,
            week_index=7,
            trajectory_label="declining",
            confidence=0.92,
            contributing_indicators=["drop_clicks_w6", "drop_clicks_w7"],
        ),
        TrajectoryRecord(
            pid=pids[2],
            course_id=course_id,
            week_index=7,
            trajectory_label="stable",
            confidence=0.75,
            contributing_indicators=["no_activity_7w"],
        ),
    ]

    return behavior_records, trajectories


def test_plot_trajectories_generates_png(tmp_path, sample_behavior_and_trajectories):
    """Verify that plotting 3 students produces a non-empty PNG file without errors."""
    records, trajectories = sample_behavior_and_trajectories
    out_path = tmp_path / "trajectories.png"

    plot_trajectories(
        behavior_records=records,
        trajectories=trajectories,
        out_path=out_path,
        title="Component 2 trajectories, course DEMO_C2, week 7",
    )

    assert out_path.exists(), "Plot PNG was not created."
    assert out_path.is_file(), "Plot path is not a file."
    assert out_path.stat().st_size > 0, "Plot PNG is empty (0 bytes)."


def test_plot_all_zero_clicks_student_no_exception(tmp_path):
    """Verify that a student with strictly zero clicks across all weeks plots without error."""
    pid = "STU_99990000"
    course_id = "DEMO_C2"
    records = [
        BehaviorRecord(
            pid=pid,
            course_id=course_id,
            week_index=w,
            login_count=0,
            session_minutes=0.0,
            clicks=0,
            video_play_count=0,
            video_pause_count=0,
            video_rewind_count=0,
            video_skip_count=0,
            video_completion_pct=0.0,
            submissions_count=0,
            avg_submission_delay_hours=0.0,
        )
        for w in range(8)
    ]
    trajectories = [
        TrajectoryRecord(
            pid=pid,
            course_id=course_id,
            week_index=7,
            trajectory_label="declining",
            confidence=0.95,
            contributing_indicators=["zero_engagement"],
        )
    ]

    out_path = tmp_path / "zero_clicks.png"
    plot_trajectories(
        behavior_records=records,
        trajectories=trajectories,
        out_path=str(out_path),
        title="Zero Clicks Test",
    )

    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_four_labels_and_grid(tmp_path):
    """Verify that 4 students with all distinct labels (stable, improving, declining, volatile) render in a grid."""
    pids = ["STU_0001aaaa", "STU_0002bbbb", "STU_0003cccc", "STU_0004dddd"]
    labels = ["stable", "improving", "declining", "volatile"]
    course_id = "TEST_C2"

    records = []
    for pid in pids:
        for w in range(6):
            records.append(
                BehaviorRecord(
                    pid=pid,
                    course_id=course_id,
                    week_index=w,
                    login_count=2,
                    session_minutes=30.0,
                    clicks=10 * (w + 1),
                    video_play_count=1,
                    video_pause_count=0,
                    video_rewind_count=0,
                    video_skip_count=0,
                    video_completion_pct=50.0,
                    submissions_count=1,
                    avg_submission_delay_hours=0.0,
                )
            )

    trajectories = [
        TrajectoryRecord(
            pid=pid,
            course_id=course_id,
            week_index=5,
            trajectory_label=label,
            confidence=0.85,
            contributing_indicators=[f"indicator_{label}"],
        )
        for pid, label in zip(pids, labels)
    ]

    out_path = tmp_path / "four_labels_grid.png"
    plot_trajectories(
        behavior_records=records,
        trajectories=trajectories,
        out_path=out_path,
        title="Component 2 Four Labels Grid Test",
    )

    assert out_path.exists()
    assert out_path.stat().st_size > 0
