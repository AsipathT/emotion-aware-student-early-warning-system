"""
backend/app/models/user.py

MongoDB User document models and roles (Feature 1 & Feature 40).
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class UserRole(str, enum.Enum):
    """Account authorization roles."""
    STUDENT = "student"
    LECTURER = "lecturer"
    COUNSELLOR = "counsellor"
    ADMIN = "admin"


class User(BaseModel):
    """
    Representation of a user account stored in MongoDB 'users' collection.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: str
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.STUDENT
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile: Optional[Any] = None
    student_id: Optional[str] = None
    pid: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        uid = str(self.id)
        doc = {
            "_id": uid,
            "id": uid,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "full_name": self.full_name,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "profile": self.profile,
        }
        if self.student_id:
            doc["student_id"] = self.student_id
        if self.pid:
            doc["pid"] = self.pid
        return doc

