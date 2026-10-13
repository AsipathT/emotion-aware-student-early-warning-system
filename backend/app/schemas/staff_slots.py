"""
backend/app/schemas/staff_slots.py

Feature 38-B: Staff Counselling Slot Schemas.
Provides request and response validation for appointment slot publishing,
slot availability queries, and confidentiality masking of location/link fields.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class SlotCreateRequest(BaseModel):
    """Payload for counsellor publishing a new appointment slot."""
    start_at: datetime = Field(..., description="Slot start date and time in UTC (must be in the future)")
    duration_minutes: int = Field(default=45, ge=15, le=120, description="Session length in minutes (15-120)")
    mode: Literal["in_person", "online"] = Field(
        default="online",
        description="Appointment delivery mode: in_person | online",
    )
    location_or_link: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Confidential location or video link (1-200 chars)",
    )

    @field_validator("start_at")
    @classmethod
    def check_future_time(cls, v: datetime) -> datetime:
        # Standardize timezone to UTC
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        if v <= now_utc:
            raise ValueError("Slot start time must be in the future.")
        return v

    @field_validator("location_or_link")
    @classmethod
    def strip_location(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Location or meeting link cannot be blank.")
        return s


class SlotResponse(BaseModel):
    """Counselling slot representation."""
    id: str
    counsellor_id: str
    counsellor_name: Optional[str] = None
    start_at: datetime
    duration_minutes: int
    mode: str
    location_or_link: Optional[str] = None
    is_booked: bool = False
    booked_by_user_id: Optional[str] = None
    intervention_id: Optional[str] = None
    booked_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class SlotListResponse(BaseModel):
    """List of counselling slots."""
    items: List[SlotResponse]
    total_count: int


class SlotBookRequest(BaseModel):
    """Payload for student booking an available counselling slot."""
    slot_id: str = Field(..., min_length=1, description="ID of open slot to book")
