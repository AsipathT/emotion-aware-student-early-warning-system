"""
backend/app/models/course.py

MongoDB Course and Module document models (Feature 3).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Module(BaseModel):
    """
    Learning module or weekly unit embedded within a Course document.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: uuid.UUID
    title: str
    content_payload: Optional[Any] = Field(default_factory=dict)
    sequence_order: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    def to_mongo(self) -> dict:
        """Converts module to dictionary for MongoDB array insertion."""
        mid = str(self.id)
        cid = str(self.course_id)
        return {
            "_id": mid,
            "id": mid,
            "course_id": cid,
            "title": self.title,
            "content_payload": self.content_payload,
            "sequence_order": self.sequence_order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Course(BaseModel):
    """
    Course document stored in MongoDB 'courses' collection.
    Modules are embedded directly inside the document.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    description: Optional[str] = None
    lecturer_id: uuid.UUID
    is_published: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modules: List[Module] = Field(default_factory=list)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    def to_mongo(self) -> dict:
        """Converts course to dictionary for MongoDB insertion."""
        cid = str(self.id)
        lid = str(self.lecturer_id)
        return {
            "_id": cid,
            "id": cid,
            "title": self.title,
            "description": self.description,
            "lecturer_id": lid,
            "is_published": self.is_published,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "modules": [m.to_mongo() if hasattr(m, "to_mongo") else m for m in self.modules],
        }
