"""
backend/app/schemas/support_student.py

Feature 38-A: Student Support Hub Schemas (Component 4 Uptake Metric).
Strictly separates student-facing supportive views from internal predictive analytics.
Never exposes PID, risk tiers, scores, or staff clinical notes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DeclineReason(str, Enum):
    """Reason chips for declining offered support."""
    NO_TIME = "no_time"
    NOT_NEEDED = "not_needed"
    PREFER_OTHER_SUPPORT = "prefer_other_support"
    OTHER = "other"


class StudentSupportInterventionItem(BaseModel):
    """Student-facing support intervention item."""
    id: str
    student_label: str
    description: str
    status: str
    delivery_module: str
    scheduled_for: Optional[datetime] = None
    offered_at: Optional[datetime] = None
    assigned_staff_name: Optional[str] = None
    student_response: Optional[Dict[str, Any]] = None

    # Extension placeholders for Parts B, C, D
    slot: Optional[Dict[str, Any]] = None
    resources: Optional[List[Dict[str, Any]]] = None
    mentor: Optional[Dict[str, Any]] = None

    model_config = {
        "from_attributes": True,
    }


class StudentSupportListResponse(BaseModel):
    """List response of student's own support interventions."""
    items: List[StudentSupportInterventionItem]
    total_count: int


class StudentSupportResponseRequest(BaseModel):
    """Request payload for student accepting or declining an offered intervention."""
    response: Literal["accept", "decline"]
    decline_reason: Optional[DeclineReason] = Field(
        default=None,
        description="Optional categorical chip when declining (no free-text)",
    )


class StudentSupportResponseResult(BaseModel):
    """Response returned upon accepting or declining support."""
    id: str
    status: str
    student_response: Dict[str, Any]
    message: str


class StudentSharedResourceItem(BaseModel):
    """Student-facing view of a shared resource or guidance material (Feature 38-C)."""
    id: str
    resource_id: str
    title: str
    description: str
    resource_type: str
    type: str
    url: Optional[str] = None
    contact_info: Optional[str] = None
    message: Optional[str] = None
    shared_at: Optional[datetime] = None
    viewed: bool = False
    viewed_at: Optional[datetime] = None


class MarkResourceViewedResponse(BaseModel):
    """Response returned when student views or marks a shared resource (Feature 38-C)."""
    success: bool
    resource_id: str
    viewed_at: Optional[datetime] = None


class BookedSlotItem(BaseModel):
    """Student-facing view of their confirmed counselling appointment (Feature 38-B)."""
    id: str
    counsellor_id: str
    counsellor_name: Optional[str] = None
    start_at: datetime
    duration_minutes: int
    mode: str
    location_or_link: Optional[str] = None
    booked_at: Optional[datetime] = None


class AvailableSlotItem(BaseModel):
    """Student-facing view of open available counselling slots (Feature 38-B). Location/link masked."""
    id: str
    counsellor_id: str
    counsellor_name: Optional[str] = None
    start_at: datetime
    duration_minutes: int
    mode: str


class AvailableSlotListResponse(BaseModel):
    """List of open available counselling slots."""
    items: List[AvailableSlotItem]
    total_count: int


class SlotBookingResult(BaseModel):
    """Response returned upon student booking an appointment slot."""
    success: bool
    slot: BookedSlotItem
    intervention_id: str
    status: str
    message: str


class SlotCancelResult(BaseModel):
    """Response returned upon student cancelling their booked appointment."""
    success: bool
    message: str


