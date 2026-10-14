"""
backend/app/models/notification.py

Feature 37: Student Notification Data Model.
Captures supportive student communications, advisor appointments,
and study resources without revealing underlying risk analytics (Component 4 Uptake Path).
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, Field

COL_NOTIFICATIONS = "notifications"

# Notification template and category types
TYPE_SUPPORT_OFFERED = "support_offered"
TYPE_APPOINTMENT_CONFIRMED = "appointment_confirmed"
TYPE_MENTOR_ASSIGNED = "mentor_assigned"
TYPE_RESOURCE_SHARED = "resource_shared"
TYPE_FEEDBACK_REQUEST = "feedback_request"


class Notification(BaseModel):
    """
    Representation of an in-app student notification stored in MongoDB `notifications`.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    type: str
    title: str
    body: str
    link: Optional[str] = None
    related_id: Optional[str] = None
    dedupe_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }
