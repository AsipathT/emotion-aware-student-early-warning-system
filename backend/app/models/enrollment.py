"""
backend/app/models/enrollment.py

MongoDB Enrollment document model (Feature 4).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class Enrollment(BaseModel):
    """
    Enrollment document stored in MongoDB 'enrollments' collection.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    student_id: uuid.UUID
    course_id: uuid.UUID
    status: str = "active"
    enrolled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    course: Optional[Any] = None
    student: Optional[Any] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    def to_mongo(self) -> dict:
        """Converts enrollment to dictionary for MongoDB insertion."""
        eid = str(self.id)
        sid = str(self.student_id)
        cid = str(self.course_id)
        return {
            "_id": eid,
            "id": eid,
            "student_id": sid,
            "course_id": cid,
            "status": self.status,
            "enrolled_at": self.enrolled_at,
            "updated_at": self.updated_at,
        }
