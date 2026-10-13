"""
backend/app/models/intervention_feedback.py

Feature 39: Student Feedback on Interventions ("Did it help?").
Defines model and constants for collection `intervention_feedback`.
Captures student-reported helpfulness, attendance, barriers, and private comments
to complement staff outcome recording (F35) and support Component 4 feedback loop.
"""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field

COL_INTERVENTION_FEEDBACK = "intervention_feedback"

AttendedStatus = Literal["yes", "partly", "no"]
FeedbackBarrier = Literal["time", "not_relevant", "uncomfortable", "technical", "other"]


class InterventionFeedback(BaseModel):
    """
    Feedback submission document stored in `intervention_feedback`.
    Free-text comment is scrubbed prior to storage and kept private (excluded from exports).
    """
    id: str = Field(..., description="Unique UUID identifier for the feedback submission")
    intervention_id: str = Field(..., description="Unique intervention record ID (1-to-1 relationship)")
    pid: str = Field(..., description="Pseudonymized student identifier (STU_xxxxxxxx)")
    intervention_type: str = Field(..., description="Type of intervention evaluated")
    helpfulness: int = Field(..., ge=1, le=5, description="Student-rated helpfulness score (1 to 5 stars)")
    attended: AttendedStatus = Field(..., description="Attendance status: yes, partly, or no")
    barrier: Optional[FeedbackBarrier] = Field(
        default=None,
        description="Optional categorical barrier if attendance/experience was hindered",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Private feedback comment, sanitized with scrub_text before storage",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of feedback submission",
    )

    model_config = {
        "from_attributes": True,
    }
