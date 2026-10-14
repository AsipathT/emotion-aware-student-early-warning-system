"""
backend/tests/test_feature39_feedback.py

Feature 39: Student Feedback on Interventions Unit Tests.
Validates:
  - Data model and schema validation constraints (helpfulness 1-5, attended states, barrier types).
  - Comment length and scrubbing safety.
  - build_observed_change_text integration with student-rated helpfulness.
  - Export schema privacy invariant (no free-text comment, no real names).
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.intervention_feedback import InterventionFeedback
from app.schemas.staff_feedback import (
    FeedbackExportResponse,
    FeedbackExportRow,
    FeedbackSummaryResponse,
    StaffFeedbackDetailResponse,
)
from app.schemas.support_student import StudentFeedbackSubmission
from app.services.outcome_metrics import build_observed_change_text
from app.core.privacy import scrub_text


def test_intervention_feedback_model_valid():
    """Validates that a correctly populated InterventionFeedback model instantiates."""
    fb = InterventionFeedback(
        id="fb-12345",
        intervention_id="int-99999",
        pid="STU_12345678",
        intervention_type="counselling_mental_health",
        helpfulness=5,
        attended="yes",
        barrier=None,
        comment="This session was very encouraging and helped me stay on track.",
    )
    assert fb.helpfulness == 5
    assert fb.attended == "yes"
    assert fb.barrier is None
    assert fb.intervention_id == "int-99999"


def test_intervention_feedback_score_range():
    """Validates that helpfulness score enforces 1 to 5 constraint."""
    # Under lower bound (0)
    with pytest.raises(ValidationError):
        InterventionFeedback(
            id="fb-1",
            intervention_id="int-1",
            pid="STU_12345678",
            intervention_type="academic_support",
            helpfulness=0,
            attended="yes",
        )

    # Over upper bound (6)
    with pytest.raises(ValidationError):
        InterventionFeedback(
            id="fb-2",
            intervention_id="int-2",
            pid="STU_12345678",
            intervention_type="academic_support",
            helpfulness=6,
            attended="yes",
        )


def test_student_feedback_submission_schema():
    """Validates student request payload schema."""
    sub = StudentFeedbackSubmission(
        helpfulness=4,
        attended="partly",
        barrier="time",
        comment="Schedule was tight between lectures.",
    )
    assert sub.helpfulness == 4
    assert sub.attended == "partly"
    assert sub.barrier == "time"


def test_privacy_scrub_comment():
    """Validates that privacy scrub_text removes identifying patterns from comments."""
    raw = "My advisor john.smith@university.ac.uk was helpful, reg REG123456."
    scrubbed, modified = scrub_text(raw)
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "john.smith@university.ac.uk" not in scrubbed


def test_build_observed_change_text_with_feedback():
    """Validates outcome summary text formatting with student helpfulness rating."""
    delta = {
        "risk_score_delta": -0.1500,
        "tier_change": "medium->low",
        "trajectory_change": "declining->stable",
    }
    # Without feedback
    text_without = build_observed_change_text(
        delta=delta,
        category="effective",
        weeks_to_improvement=3,
        helpfulness_rating=None,
    )
    assert "effective; risk delta -0.1500 (medium->low); trajectory declining->stable; 3 weeks to improvement" in text_without
    assert "student-rated helpfulness" not in text_without

    # With feedback
    text_with = build_observed_change_text(
        delta=delta,
        category="effective",
        weeks_to_improvement=3,
        helpfulness_rating=5,
    )
    assert "student-rated helpfulness 5/5" in text_with


def test_export_row_privacy_invariant():
    """Validates that FeedbackExportRow excludes free-text comments and identities."""
    row = FeedbackExportRow(
        pid="STU_abcdef12",
        intervention_type="peer_mentoring",
        helpfulness=4,
        attended="yes",
        barrier=None,
        created_at=datetime.now(timezone.utc),
    )
    # Check model fields
    assert "comment" not in FeedbackExportRow.model_fields
    assert "user_id" not in FeedbackExportRow.model_fields
    assert "student_name" not in FeedbackExportRow.model_fields

    export_resp = FeedbackExportResponse(
        exported_at=datetime.now(timezone.utc),
        total_count=1,
        data=[row],
    )
    dumped = export_resp.model_dump(by_alias=True)
    assert dumped["schema"] == "feedback-export-1.0"
    assert len(dumped["data"]) == 1
    assert "comment" not in dumped["data"][0]
