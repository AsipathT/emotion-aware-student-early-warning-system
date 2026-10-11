"""
backend/app/schemas/journal.py

Pydantic v2 request / response schemas for Reflective Learning Journal (Feature 16).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class JournalEntryCreate(BaseModel):
    """Payload sent by student when submitting a weekly reflective journal entry."""

    course_id: str
    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        # Strip leading and trailing whitespace ONLY (do not collapse inner whitespace or strip emojis)
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Journal entry must be at least 10 characters long.")
        if len(stripped) > 5000:
            raise ValueError("Journal entry cannot exceed 5000 characters.")
        return stripped


class JournalCurrentResponse(BaseModel):
    """Weekly submission status for a student in a specific course."""

    course_id: str
    week_start: datetime
    week_end: datetime
    submitted: bool
    entry_id: Optional[str] = None

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    """Reflective journal entry representation returned to the student."""

    id: uuid.UUID
    author_id: str
    author_role: str
    course_id: str
    source_type: str = "journal"
    week_start: datetime
    body: str
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
