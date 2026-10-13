"""
backend/app/schemas/staff_feedback.py

Feature 39: Staff Feedback Schemas (Component 4 Feedback Loop).
Defines schemas for:
  - GET /api/v1/staff/feedback/interventions/{id} (Feedback detail panel)
  - GET /api/v1/staff/feedback/summary (Aggregate uptake & helpfulness metrics)
  - GET /api/v1/staff/feedback/export (Admin-only pseudonymous, comment-free research export)
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.models.intervention_feedback import AttendedStatus, FeedbackBarrier


class StaffFeedbackDetailResponse(BaseModel):
    """Staff-facing view of a student's feedback submission on an intervention."""
    id: str
    intervention_id: str
    pid: str
    intervention_type: str
    helpfulness: int = Field(..., ge=1, le=5)
    attended: AttendedStatus
    barrier: Optional[FeedbackBarrier] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class FeedbackSummaryResponse(BaseModel):
    """Aggregate statistics for student-reported intervention feedback."""
    n: int = Field(..., description="Total feedback submissions count")
    completed_interventions: int = Field(..., description="Total count of completed interventions")
    response_rate: float = Field(..., description="Response rate (feedback count / completed interventions)")
    mean_helpfulness: float = Field(..., description="Mean helpfulness rating across all feedback (1-5)")
    mean_helpfulness_by_type: Dict[str, float] = Field(
        default_factory=dict,
        description="Mean helpfulness rating broken down by intervention type",
    )
    barrier_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of reported barriers (e.g., time, not_relevant, uncomfortable)",
    )
    attended_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of attendance confirmations (yes, partly, no)",
    )


class FeedbackExportRow(BaseModel):
    """
    Pseudonymized export row for research analysis.
    STRICT PRIVACY: Excludes free-text comments and student names.
    """
    pid: str = Field(..., description="Pseudonymized student ID (STU_xxxxxxxx)")
    intervention_type: str = Field(..., description="Categorical intervention type")
    helpfulness: int = Field(..., ge=1, le=5, description="Student helpfulness score")
    attended: str = Field(..., description="Attendance status")
    barrier: Optional[str] = Field(None, description="Reported barrier (if any)")
    created_at: datetime = Field(..., description="Timestamp of submission")


class FeedbackExportResponse(BaseModel):
    """Audit-logged administrative export response adhering to Component 4 contract format."""
    schema_version: Literal["feedback-export-1.0"] = Field(
        default="feedback-export-1.0",
        alias="schema",
        description="Data contract schema version identifier",
    )
    exported_at: datetime
    total_count: int
    data: List[FeedbackExportRow]

    model_config = {
        "populate_by_name": True,
    }

