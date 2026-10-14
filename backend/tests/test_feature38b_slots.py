"""
backend/tests/test_feature38b_slots.py

Feature 38-B: Unit tests for counselling slots schemas, validations, and privacy models.
NOTE: As per standing rules, these tests are written but NOT run during pairing execution.
"""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.models.support_slot import CounsellingSlot
from app.schemas.staff_slots import (
    SlotBookRequest,
    SlotCreateRequest,
    SlotResponse,
)
from app.schemas.support_student import (
    AvailableSlotItem,
    BookedSlotItem,
)


def test_slot_create_valid():
    """Verifies valid slot creation with future start date."""
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    req = SlotCreateRequest(
        start_at=future_time,
        duration_minutes=45,
        mode="online",
        location_or_link="https://meet.google.com/abc-defg-hij",
    )
    assert req.duration_minutes == 45
    assert req.mode == "online"
    assert req.location_or_link == "https://meet.google.com/abc-defg-hij"


def test_slot_create_rejects_past_time():
    """Verifies that start times in the past are rejected."""
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    with pytest.raises(ValidationError) as exc_info:
        SlotCreateRequest(
            start_at=past_time,
            duration_minutes=45,
            mode="online",
            location_or_link="https://meet.google.com/abc-defg-hij",
        )
    assert "start_at must be in the future" in str(exc_info.value)


def test_slot_create_validates_duration_range():
    """Verifies that duration must be between 15 and 120 minutes."""
    future_time = datetime.now(timezone.utc) + timedelta(days=1)

    # Rejects duration < 15
    with pytest.raises(ValidationError):
        SlotCreateRequest(
            start_at=future_time,
            duration_minutes=10,
            mode="online",
            location_or_link="Room 101",
        )

    # Rejects duration > 120
    with pytest.raises(ValidationError):
        SlotCreateRequest(
            start_at=future_time,
            duration_minutes=150,
            mode="online",
            location_or_link="Room 101",
        )


def test_slot_create_validates_location_or_link_length():
    """Verifies location_or_link is non-empty and <= 200 characters."""
    future_time = datetime.now(timezone.utc) + timedelta(days=1)

    # Empty string rejected
    with pytest.raises(ValidationError):
        SlotCreateRequest(
            start_at=future_time,
            duration_minutes=30,
            mode="in_person",
            location_or_link="   ",
        )

    # Over 200 characters rejected
    with pytest.raises(ValidationError):
        SlotCreateRequest(
            start_at=future_time,
            duration_minutes=30,
            mode="in_person",
            location_or_link="A" * 201,
        )


def test_slot_book_request_requires_slot_id():
    """Verifies SlotBookRequest validates slot_id."""
    req = SlotBookRequest(slot_id="slot-uuid-1234")
    assert req.slot_id == "slot-uuid-1234"

    with pytest.raises(ValidationError):
        SlotBookRequest(slot_id="   ")


def test_confidentiality_model_exclusion():
    """
    Verifies that AvailableSlotItem strictly does NOT expose location_or_link to the public directory,
    while BookedSlotItem contains location_or_link for the student who confirmed the appointment.
    """
    future_time = datetime.now(timezone.utc) + timedelta(days=3)

    available_slot = AvailableSlotItem(
        id="slot-avail-1",
        counsellor_id="counsellor-001",
        counsellor_name="Dr. Taylor",
        start_at=future_time,
        duration_minutes=45,
        mode="online",
    )
    # Available slot must NOT contain location_or_link field
    assert not hasattr(available_slot, "location_or_link")
    dumped = available_slot.model_dump()
    assert "location_or_link" not in dumped

    # Booked slot contains confidential location_or_link
    booked_slot = BookedSlotItem(
        id="slot-booked-1",
        counsellor_id="counsellor-001",
        counsellor_name="Dr. Taylor",
        start_at=future_time,
        duration_minutes=45,
        mode="online",
        location_or_link="https://meet.google.com/confidential-link",
        booked_at=datetime.now(timezone.utc),
    )
    assert hasattr(booked_slot, "location_or_link")
    assert booked_slot.location_or_link == "https://meet.google.com/confidential-link"


def test_counselling_slot_entity_model():
    """Verifies CounsellingSlot storage model default fields and serialization."""
    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    slot = CounsellingSlot(
        counsellor_id="counsellor-999",
        start_at=future_time,
        duration_minutes=60,
        mode="in_person",
        location_or_link="Wellbeing Suite 204",
    )
    assert slot.id is not None
    assert slot.booked_by_user_id is None
    assert slot.intervention_id is None
    assert slot.booked_at is None
    assert slot.cancelled_at is None
    assert slot.duration_minutes == 60
    assert slot.location_or_link == "Wellbeing Suite 204"
