"""
backend/app/schemas/auth.py

Pydantic v2 request / response schemas for the authentication endpoints.

Schema map
----------
  RegisterRequest      →  POST /api/v1/auth/register  (body)
  LoginRequest         →  POST /api/v1/auth/login      (body)
  TokenResponse        →  POST /api/v1/auth/login      (response)
                          POST /api/v1/auth/refresh     (response)
  TokenRefreshRequest  →  POST /api/v1/auth/refresh    (body)
  UserResponse         →  POST /api/v1/auth/register  (response)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


# ── Request schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Payload required to create a new user account."""

    email: EmailStr = Field(
        ...,
        examples=["student@university.edu"],
        description="Must be a valid e-mail address; used as the login identifier.",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        examples=["Str0ng!Pass"],
        description="Min 8 chars, at least one uppercase letter and one digit.",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["Alice Tan"],
    )
    role: UserRole = Field(
        default=UserRole.STUDENT,
        description="Account role. Defaults to 'student'.",
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce a minimum password complexity policy."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("full_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    """Credentials for obtaining a token pair."""

    email: EmailStr = Field(..., examples=["student@university.edu"])
    password: str = Field(..., examples=["Str0ng!Pass"])


class TokenRefreshRequest(BaseModel):
    """Body for the token-refresh endpoint."""

    refresh_token: str = Field(
        ...,
        description="A valid, unexpired refresh JWT issued by /login or /refresh.",
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Returned after a successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Safe representation of a user account (no password hash)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
