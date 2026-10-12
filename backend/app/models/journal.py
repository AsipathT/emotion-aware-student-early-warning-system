"""
backend/app/models/journal.py

MongoDB document model for Reflective Learning Journal entries (Feature 16).

Collection: journal_entries
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field


class JournalEntry(BaseModel):
    """Document stored in the ``journal_entries`` collection."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    author_id: str
    author_role: str = "student"
    course_id: str
    source_type: str = "journal"
    week_start: datetime
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True, "populate_by_name": True}

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        jid = str(self.id)
        return {
            "_id": jid,
            "id": jid,
            "author_id": self.author_id,
            "author_role": self.author_role,
            "course_id": self.course_id,
            "source_type": self.source_type,
            "week_start": self.week_start,
            "body": self.body,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
