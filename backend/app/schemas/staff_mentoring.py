"""
backend/app/schemas/staff_mentoring.py

Feature 38-D: Staff Peer Mentoring Schemas.
Request and response models for candidate search, assignment creation, and lifecycle termination.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CandidateStudent(BaseModel):
    """Candidate student available for peer mentor assignment (ID and full name only)."""
    id: str
    full_name: str


class CandidateListResponse(BaseModel):
    """List of candidate students matching query."""
    items: List[CandidateStudent]
    total_count: int


class AssignMentorRequest(BaseModel):
    """Payload to pair a peer mentor with an accepted mentee intervention."""
    mentor_user_id: str = Field(..., description="User ID of the student assigned as mentor")

    @field_validator("mentor_user_id")
    @classmethod
    def validate_mentor_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("mentor_user_id must be a non-empty string.")
        return s


class MentoringAssignmentResponse(BaseModel):
    """Staff view of a mentoring assignment."""
    id: str
    intervention_id: str
    mentee_user_id: str
    mentee_name: Optional[str] = None
    mentor_user_id: str
    mentor_name: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    ended_at: Optional[datetime] = None
