"""
backend/app/schemas/admin.py

Pydantic v2 schemas for the Admin Panel (Feature 40).
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.user import UserRole
from app.schemas.profile import ProfileResponse


class SystemStatsResponse(BaseModel):
    """System-wide metrics and resource counts for the Admin Panel."""

    total_users: int = Field(..., description="Total registered user accounts across all roles.")
    active_users: int = Field(..., description="Count of currently active (non-suspended) users.")
    total_courses: int = Field(..., description="Total academic courses registered on the platform.")
    published_courses: int = Field(..., description="Count of published and catalog-visible courses.")
    total_students: int = Field(default=0, description="Count of student accounts.")
    total_lecturers: int = Field(default=0, description="Count of lecturer/instructor accounts.")


class UserStatusUpdate(BaseModel):
    """Payload to activate or suspend a specific user account."""

    is_active: bool = Field(..., description="True to activate account; False to suspend.")


class UserRoleUpdate(BaseModel):
    """Payload to update a user's authorization role."""

    role: UserRole = Field(..., description="New role assigned to the user.")


class AdminUserResponse(BaseModel):
    """Administrative representation of a user account with nested profile."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    profile: Optional[ProfileResponse] = None

    model_config = {"from_attributes": True}
