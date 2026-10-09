"""
backend/app/models/enrollment.py

SQLAlchemy 2.0 model for student course enrollments (Feature 4).

Relationships
-------------
  User (Student) 1 ──< * Enrollment
  Course         1 ──< * Enrollment
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.user import User


class Enrollment(Base):
    """
    Associative enrollment entity linking a student to an academic course.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_id",
            name="uq_enrollment_student_course",
        ),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign keys ──────────────────────────────────────────────────────────
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Enrollment status ─────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
        index=True,
        comment="Enrollment state: active, completed, or dropped.",
    )

    # ── Strict UTC Timestamps ─────────────────────────────────────────────────
    enrolled_at: Mapped[datetime] = mapped_column(
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

    # ── Reciprocal Relationships ──────────────────────────────────────────────
    student: Mapped["User"] = relationship(
        "User",
        back_populates="enrollments",
        lazy="noload",
    )
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="enrollments",
        lazy="noload",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Enrollment id={self.id} student_id={self.student_id} "
            f"course_id={self.course_id} status={self.status!r}>"
        )
