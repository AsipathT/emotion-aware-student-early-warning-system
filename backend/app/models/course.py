"""
backend/app/models/course.py

SQLAlchemy 2.0 models for Course and Module management.

Relationships
-------------
  User (Lecturer) 1 ──< * Course
  Course          1 ──< * Module
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.enrollment import Enrollment
    from app.models.user import User


class Course(Base):
    """
    Academic course managed by a lecturer or administrator.
    """

    __tablename__ = "courses"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Core details ──────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Ownership (Lecturer) ──────────────────────────────────────────────────
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Visibility ────────────────────────────────────────────────────────────
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    # ── UTC Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    lecturer: Mapped["User"] = relationship(
        "User",
        back_populates="courses_taught",
        lazy="noload",
    )

    modules: Mapped[List["Module"]] = relationship(
        "Module",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Module.sequence_order",
        lazy="noload",
    )

    enrollments: Mapped[List["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Course id={self.id} title={self.title!r} published={self.is_published}>"


class Module(Base):
    """
    Learning module or week-by-week unit within a Course.
    """

    __tablename__ = "modules"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Parent course ─────────────────────────────────────────────────────────
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Module details ────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content_payload: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Structured learning content, assignments, resources, or metadata.",
    )
    sequence_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # ── UTC Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="modules",
        lazy="noload",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Module id={self.id} course_id={self.course_id} title={self.title!r}>"
