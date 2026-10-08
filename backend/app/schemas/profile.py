"""
backend/app/schemas/profile.py

Pydantic v2 schemas for user profile endpoints.

Schema map
----------
  ProfileUpdate       →  PUT  /api/v1/users/me/profile  (request body)
  ProfileResponse     →  Profile sub-object embedded in user responses
  UserMeResponse      →  GET  /api/v1/users/me           (full response)
  UserDetailResponse  →  GET  /api/v1/users/{user_id}    (admin/counsellor view)
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.user import UserRole


# ── Profile schemas ───────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    """
    All fields are optional so callers can do a partial update (PATCH-style
    semantics over PUT).  Fields set to `None` explicitly clear the value.
    Fields omitted from the payload are left unchanged.
    """

    student_id: Optional[str] = Field(
        default=None,
        max_length=100,
        examples=["STU-2024-0042"],
        description="Institutional student registration number. Leave blank for staff.",
    )
    department: Optional[str] = Field(
        default=None,
        max_length=255,
        examples=["Faculty of Computing"],
    )
    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
        examples=["Final-year Computer Science student interested in AI."],
    )
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        examples=["https://cdn.example.com/avatars/alice.png"],
        description="Publicly accessible URL to the user's avatar image.",
    )

    @field_validator("bio")
    @classmethod
    def strip_bio(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("student_id", "department")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class ProfileResponse(BaseModel):
    """Serialised profile returned inside user responses."""

    id: uuid.UUID
    student_id: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Composite user + profile schemas ─────────────────────────────────────────

class UserMeResponse(BaseModel):
    """
    Full response for GET /api/v1/users/me.
    Embeds the profile if one exists, or null otherwise.
    """

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


class UserDetailResponse(BaseModel):
    """
    Response for GET /api/v1/users/{user_id}.
    Accessible only by Admin and Counsellor roles.
    Includes profile and a subset of account metadata.
    """

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
