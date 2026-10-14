"""
backend/app/models/support_mentoring.py

Feature 38-D: Peer Mentoring Assignment Model (Component 4 Intervention Delivery).
Persisted in collection `mentoring_assignments`.
Enforces strict student privacy:
  - Mentee must have accepted support before matching.
  - Mentors see only mentee display name (no intervention reasons or analytics).
"""

from datetime import datetime, timezone
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field

COL_MENTORING_ASSIGNMENTS = "mentoring_assignments"

MENTORING_STATUS_ACTIVE = "active"
MENTORING_STATUS_ENDED = "ended"

MentoringStatus = Literal["active", "ended"]


class MentoringAssignment(BaseModel):
    """
    Peer mentoring pairing entity connecting an accepted student mentee with a peer mentor student.
    Stored in `mentoring_assignments`.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        alias="_id",
        description="Unique identifier for the mentoring assignment",
    )
    intervention_id: str = Field(..., description="ID of the associated peer_mentoring intervention record")
    mentee_user_id: str = Field(..., description="User ID of the mentee student")
    mentor_user_id: str = Field(..., description="User ID of the assigned mentor student")
    status: MentoringStatus = Field(default=MENTORING_STATUS_ACTIVE, description="Assignment status: active | ended")
    created_by: str = Field(..., description="User ID of staff counsellor or admin who created the assignment")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = Field(default=None, description="Timestamp when assignment was concluded by staff")

    class Config:
        populate_by_name = True
