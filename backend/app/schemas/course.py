"""
backend/app/schemas/course.py

Pydantic v2 schemas for Course and Module management endpoints.

Schema map
----------
  ModuleCreate     →  POST /api/v1/courses/{course_id}/modules  (body)
  ModuleResponse   →  Module representation
  CourseCreate     →  POST /api/v1/courses                    (body)
  CourseUpdate     →  PATCH/PUT /api/v1/courses/{course_id}   (body)
  CourseResponse   →  Course representation with nested modules
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Module Schemas ────────────────────────────────────────────────────────────

class ModuleCreate(BaseModel):
    """Payload to create a new module under an existing course."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["Week 1: Introduction to Data Structures"],
    )
    content_payload: Optional[Any] = Field(
        default_factory=dict,
        description="Structured module learning materials, syllabus, or metadata in JSON format.",
        examples=[{"topics": ["Arrays", "Linked Lists"], "reading_time_mins": 45}],
    )
    sequence_order: int = Field(
        default=1,
        ge=1,
        description="Ordering index for displaying modules chronologically or sequentially.",
        examples=[1],
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Module title cannot be blank or whitespace only.")
        return stripped


class ModuleResponse(BaseModel):
    """Public representation of a course module."""

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    content_payload: Optional[Any] = None
    sequence_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Course Schemas ────────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    """Payload to register a new course."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["CS101: Introduction to Computer Science"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        examples=["Foundational computing concepts, algorithms, and Python programming."],
    )
    is_published: bool = Field(
        default=False,
        description="Whether the course is visible to enrolled students or public catalog.",
    )
    lecturer_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Instructor ID. Defaults to current user if lecturer. Admins can assign to any lecturer.",
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Course title cannot be blank or whitespace only.")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_desc(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class CourseUpdate(BaseModel):
    """Payload for updating course metadata."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
    )
    is_published: Optional[bool] = Field(
        default=None,
    )
    lecturer_id: Optional[uuid.UUID] = Field(
        default=None,
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Course title cannot be blank.")
            return stripped
        return v


class CourseResponse(BaseModel):
    """Detailed course representation including its modules."""

    id: uuid.UUID
    title: str
    description: Optional[str] = None
    lecturer_id: uuid.UUID
    is_published: bool
    created_at: datetime
    updated_at: datetime
    modules: List[ModuleResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
