"""
backend/app/schemas/enrollment.py

Pydantic v2 schemas for Enrollment management (Feature 4).
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.user import UserRole
from app.schemas.profile import ProfileResponse


# ── Nested representation schemas ─────────────────────────────────────────────

class EnrollmentCourseSummary(BaseModel):
    """Concise course representation embedded within an enrollment."""

    id: uuid.UUID
    title: str
    description: Optional[str] = None
    lecturer_id: uuid.UUID
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollmentStudentSummary(BaseModel):
    """Student account & profile details embedded in an enrollment roster."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    profile: Optional[ProfileResponse] = None

    model_config = {"from_attributes": True}


# ── Enrollment request & response schemas ─────────────────────────────────────

class EnrollmentCreate(BaseModel):
    """Payload to initiate a course enrollment."""

    status: Optional[str] = Field(
        default="active",
        max_length=50,
        description="Initial enrollment state (active, completed, dropped).",
    )


class EnrollmentUpdate(BaseModel):
    """Payload to alter an enrollment's status."""

    status: str = Field(
        ...,
        max_length=50,
        description="New enrollment status: active, completed, or dropped.",
    )


class EnrollmentResponse(BaseModel):
    """Serialised enrollment entity with nested course and student details."""

    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    status: str
    enrolled_at: datetime
    updated_at: datetime
    course: Optional[EnrollmentCourseSummary] = None
    student: Optional[EnrollmentStudentSummary] = None

    model_config = {"from_attributes": True}
