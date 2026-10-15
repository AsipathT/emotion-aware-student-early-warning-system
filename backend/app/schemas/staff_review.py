"""
backend/app/schemas/staff_review.py

Pydantic schemas for Feature 33: Human-in-the-Loop Recommendation Review (C4 FR7).
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class StaffReviewRequest(BaseModel):
    """Payload submitted by authorized staff to review a recommendation."""
    decision: Literal["approved", "modified", "rejected"] = Field(
        ...,
        description="Staff decision: approved, modified, or rejected",
    )
    selected_rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="Selected candidate rank (required when decision is 'approved')",
    )
    modified_intervention_type: Optional[str] = Field(
        default=None,
        description="Chosen alternative intervention type key (required when decision is 'modified')",
    )
    reason: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=500,
        description="Justification rationale (required for 'modified' and 'rejected', 10-500 chars)",
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Optional target course ID (defaults to course of student's risk assessment)",
    )

    @model_validator(mode="after")
    def validate_decision_requirements(self) -> "StaffReviewRequest":
        if self.decision == "approved":
            if self.selected_rank is None:
                raise ValueError("selected_rank is required when approving a recommendation.")
        elif self.decision == "modified":
            if not self.modified_intervention_type:
                raise ValueError("modified_intervention_type is required when modifying a recommendation.")
            if not self.reason or len(self.reason.strip()) < 10:
                raise ValueError("Justification reason (at least 10 characters) is required when modifying a recommendation.")
        elif self.decision == "rejected":
            if not self.reason or len(self.reason.strip()) < 10:
                raise ValueError("Justification reason (at least 10 characters) is required when rejecting a recommendation.")
        return self


class StaffReviewResponse(BaseModel):
    """Response returned upon successfully recording staff recommendation review."""
    recommendation_id: str
    decision: str
    status: str
    intervention_id: Optional[str] = None
    chosen_intervention_type: Optional[str] = None
    reviewed_at: datetime
    message: str


class StaffReviewStatsResponse(BaseModel):
    """Operational statistics reflecting the 100% human-in-the-loop review requirement."""
    total: int
    pending: int
    approved: int
    modified: int
    rejected: int
    reviewed: int
    review_rate: float
