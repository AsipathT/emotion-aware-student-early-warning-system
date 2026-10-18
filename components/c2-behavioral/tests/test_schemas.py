"""
Unit tests for Component 2 schemas and envelope generation.
"""

from datetime import datetime
import pytest
from pydantic import ValidationError

from service.schemas import BehaviorRecord, TrajectoryRecord, build_envelope


def test_valid_trajectory_record_passes():
    """Valid TrajectoryRecord passes validation."""
    rec = TrajectoryRecord(
        pid="STU_12345678",
        course_id="CS101",
        week_index=5,
        trajectory_label="stable",
        confidence=0.88,
        contributing_indicators=["clicks_rising_trend"],
    )
    assert rec.pid == "STU_12345678"
    assert rec.trajectory_label == "stable"
    assert rec.confidence == pytest.approx(0.88)


def test_bad_pid_raises():
    """Invalid PID pattern raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_invalid_pid",
            course_id="CS101",
            week_index=5,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=[],
        )


def test_capitalized_label_raises():
    """Capitalized label 'Stable' raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=5,
            trajectory_label="Stable",  # Must be lowercase
            confidence=0.8,
            contributing_indicators=[],
        )


def test_eleven_indicators_raises():
    """More than 10 indicators raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=5,
            trajectory_label="declining",
            confidence=0.8,
            contributing_indicators=["ind"] * 11,
        )


def test_negative_week_index_raises():
    """week_index < 0 raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=-1,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=[],
        )


def test_extra_field_raises():
    """Extra fields are forbidden and raise ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=5,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=[],
            extra_field="disallowed",
        )


def test_email_indicator_raises():
    """Email in indicator raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=5,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=["contact student@example.com"],
        )


def test_it_pattern_indicator_raises():
    """IT followed by 8 digits raises ValidationError."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            pid="STU_12345678",
            course_id="CS101",
            week_index=5,
            trajectory_label="stable",
            confidence=0.8,
            contributing_indicators=["ID IT12345678 noted"],
        )


def test_build_envelope_metadata():
    """build_envelope has source 'c2', schema_version '1.0', generated_at with timezone, and non-empty request_id."""
    records = [
        TrajectoryRecord(
            pid="STU_abcdef12",
            course_id="MATH101",
            week_index=4,
            trajectory_label="improving",
            confidence=0.75,
            contributing_indicators=["recent_activity_rise"],
        )
    ]
    env = build_envelope(records)

    assert env["source"] == "c2"
    assert env["schema_version"] == "1.0"
    assert len(env["request_id"]) > 0
    assert len(env["data"]) == 1

    # Check generated_at has timezone
    dt = datetime.fromisoformat(env["generated_at"])
    assert dt.tzinfo is not None
