"""
backend/app/models/intervention_record.py

Feature 33: Operational Intervention Record Model and State Machine.
Defines staff-side intervention tracking for collection `intervention_records`.
Separated from canonical `interventions` to maintain data contract boundaries
while capturing operational assignments, baseline snapshots, and audit history.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

COL_INTERVENTION_RECORDS = "intervention_records"
COL_RECOMMENDATION_REVIEWS = "recommendation_reviews"

# Operational status vocabulary
STATUS_APPROVED = "approved"
STATUS_OFFERED = "offered"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

STATUSES: List[str] = [
    STATUS_APPROVED,
    STATUS_OFFERED,
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
]

# Strict human-in-the-loop transition graph
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    STATUS_APPROVED: [STATUS_OFFERED, STATUS_CANCELLED],
    STATUS_OFFERED: [STATUS_ACCEPTED, STATUS_DECLINED, STATUS_CANCELLED],
    STATUS_DECLINED: [STATUS_OFFERED, STATUS_CANCELLED],
    STATUS_ACCEPTED: [STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CANCELLED],
    STATUS_IN_PROGRESS: [STATUS_COMPLETED, STATUS_CANCELLED],
    STATUS_COMPLETED: [],  # Terminal
    STATUS_CANCELLED: [],  # Terminal
}


def can_transition(from_status: str, to_status: str) -> bool:
    """Validates whether an operational status transition is permissible."""
    allowed = ALLOWED_TRANSITIONS.get(str(from_status).strip().lower(), [])
    return str(to_status).strip().lower() in allowed


class StatusHistoryEntry(BaseModel):
    """Historical transition audit record."""
    status: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    by: str
    note: Optional[str] = None


class InterventionNote(BaseModel):
    """Private staff counselor clinical or progress note."""
    note_id: str
    author_id: str
    author_role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SharedResourceEntry(BaseModel):
    """Resource shared with the student during intervention delivery (Feature 38-C)."""
    resource_id: str
    shared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    shared_by: str
    viewed_at: Optional[datetime] = None
    message: Optional[str] = Field(default=None, max_length=300)


class InterventionRecord(BaseModel):
    """
    Staff-side operational intervention entity persisted in `intervention_records`.
    Enables tracking of counselor assignments, student communication status,
    and baseline metric snapshots captured at approval time.
    """
    id: str = Field(..., alias="_id", description="Unique intervention identifier (matching canonical intervention_id)")
    recommendation_id: Optional[str] = Field(default=None, description="Source recommendation ID if originating from C4")
    origin: Literal["recommendation", "manual"] = Field(default="recommendation", description="Provenance of intervention")
    pid: str = Field(..., description="Pseudonymized student identifier")
    course_id: str = Field(..., description="Target academic course identifier")
    intervention_type: str = Field(..., description="Categorical intervention type key")
    status: str = Field(default=STATUS_APPROVED, description="Current lifecycle state")
    created_by: str = Field(..., description="User ID of staff member who approved/created intervention")
    assigned_to: Optional[str] = Field(default=None, description="Staff member assigned to deliver the intervention")
    scheduled_for: Optional[datetime] = Field(default=None, description="Scheduled session datetime if applicable")
    baseline_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Immutable snapshot of student risk, trajectory, and affect at approval time (C4 baseline)",
    )
    status_history: List[StatusHistoryEntry] = Field(default_factory=list)
    notes: List[InterventionNote] = Field(default_factory=list, description="Private staff counselor case notes")
    shared_resources: List[SharedResourceEntry] = Field(
        default_factory=list,
        description="Resources shared with student during delivery (F38-C)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True

