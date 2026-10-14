"""
backend/tests/test_feature38d_mentoring.py

Feature 38-D: Unit tests for peer mentoring schemas, validators, and privacy invariants.
NOTE: As per standing rules, these tests are written but NOT run during pairing execution.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.support_mentoring import MentoringAssignment, MENTORING_STATUS_ACTIVE, MENTORING_STATUS_ENDED
from app.schemas.staff_mentoring import (
    AssignMentorRequest,
    CandidateListResponse,
    CandidateStudent,
    MentoringAssignmentResponse,
)
from app.schemas.support_student import (
    MentorAssignmentItem,
    MentorAssignmentListResponse,
    StudentMentorInfo,
)


def test_assign_mentor_request_valid():
    """Verifies that non-empty mentor_user_id is validated and stripped."""
    req = AssignMentorRequest(mentor_user_id="  student-user-456  ")
    assert req.mentor_user_id == "student-user-456"


def test_assign_mentor_request_rejects_empty():
    """Verifies that empty or whitespace mentor_user_id raises ValidationError."""
    with pytest.raises(ValidationError):
        AssignMentorRequest(mentor_user_id="   ")

    with pytest.raises(ValidationError):
        AssignMentorRequest(mentor_user_id="")


def test_mentoring_assignment_entity_model():
    """Verifies MentoringAssignment storage entity default fields and status."""
    now_utc = datetime.now(timezone.utc)
    assignment = MentoringAssignment(
        intervention_id="interv-123",
        mentee_user_id="mentee-student-1",
        mentor_user_id="mentor-student-2",
        created_by="staff-counsellor-9",
    )
    assert assignment.id is not None
    assert assignment.status == MENTORING_STATUS_ACTIVE
    assert assignment.ended_at is None
    assert assignment.created_at is not None

    dumped = assignment.model_dump()
    assert dumped["intervention_id"] == "interv-123"
    assert dumped["mentor_user_id"] == "mentor-student-2"


def test_candidate_student_schemas():
    """Verifies CandidateStudent schema returns only id and full_name."""
    cand = CandidateStudent(id="cand-01", full_name="Jamie Senior")
    assert cand.id == "cand-01"
    assert cand.full_name == "Jamie Senior"

    resp = CandidateListResponse(items=[cand], total_count=1)
    assert resp.total_count == 1
    assert len(resp.items) == 1


def test_mentor_privacy_invariant_exclusion():
    """
    CRITICAL PRIVACY TEST:
    Verifies that MentorAssignmentItem provided to the mentor student:
      1. Has NO intervention_id, intervention_type, notes, or risk indicators.
      2. Exposes ONLY mentee display name, status, and pairing timestamp.
    """
    now_utc = datetime.now(timezone.utc)
    item = MentorAssignmentItem(
        id="assign-001",
        mentee_user_id="student-mentee-42",
        mentee_display_name="Jordan Mentee",
        status="active",
        since=now_utc,
    )

    # Must NOT have any sensitive fields
    assert not hasattr(item, "intervention_id")
    assert not hasattr(item, "intervention_type")
    assert not hasattr(item, "student_label")
    assert not hasattr(item, "notes")
    assert not hasattr(item, "risk_score")
    assert not hasattr(item, "affective_indicators")

    dumped = item.model_dump()
    assert "intervention_id" not in dumped
    assert "notes" not in dumped
    assert "risk_score" not in dumped
    assert dumped["mentee_display_name"] == "Jordan Mentee"
    assert dumped["status"] == "active"


def test_mentee_mentor_info_schema():
    """Verifies mentee's view of the assigned mentor."""
    info = StudentMentorInfo(
        id="assign-001",
        mentor_user_id="mentor-user-88",
        full_name="Morgan Peer Mentor",
        status="active",
        since=datetime.now(timezone.utc),
    )
    assert info.mentor_user_id == "mentor-user-88"
    assert info.full_name == "Morgan Peer Mentor"
    assert info.status == "active"
