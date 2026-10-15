"""
backend/app/models/support_slot.py

Feature 38-B: Counselling Appointment Slot Model.
Defines appointment slots published by staff counsellors and booked by students
for accepted or in-progress counselling interventions.
Persisted in collection `counselling_slots`.
"""

from datetime import datetime, timezone
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field

COL_COUNSELLING_SLOTS = "counselling_slots"

SLOT_MODE_IN_PERSON = "in_person"
SLOT_MODE_ONLINE = "online"

SlotMode = Literal["in_person", "online"]


class CounsellingSlot(BaseModel):
    """
    Counselling appointment slot entity.
    Stored in `counselling_slots`.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        alias="_id",
        description="Unique identifier for the counselling slot",
    )
    counsellor_id: str = Field(..., description="User ID of staff counsellor offering the slot")
    start_at: datetime = Field(..., description="Scheduled start time in UTC")
    duration_minutes: int = Field(default=45, ge=15, le=120, description="Session length in minutes (15-120)")
    mode: SlotMode = Field(default=SLOT_MODE_ONLINE, description="Appointment mode: in_person | online")
    location_or_link: str = Field(
        ...,
        max_length=200,
        description="Confidential location or video link (visible only to booker and counsellor)",
    )
    booked_by_user_id: Optional[str] = Field(default=None, description="User ID of student who booked the slot")
    intervention_id: Optional[str] = Field(default=None, description="Associated intervention ID")
    booked_at: Optional[datetime] = Field(default=None, description="Timestamp when slot was booked")
    cancelled_at: Optional[datetime] = Field(default=None, description="Timestamp if cancelled")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
