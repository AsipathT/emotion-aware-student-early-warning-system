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
