"""
backend/app/models/profile.py

MongoDB Profile document model (Feature 2).
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """
    Profile extension for a user stored in MongoDB.
    Can be embedded directly inside 'users' or stored in 'profiles' collection.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    student_id: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        pid = str(self.id)
        uid = str(self.user_id)
        return {
            "_id": pid,
            "id": pid,
            "user_id": uid,
            "student_id": self.student_id,
            "department": self.department,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
