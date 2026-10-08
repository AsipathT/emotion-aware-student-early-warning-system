"""
backend/app/models/user.py

SQLAlchemy 2.0 User model.

Roles
-----
  student    – learner enrolled in courses
  lecturer   – course instructor
  counsellor – student welfare / early-intervention officer
  admin      – platform administrator

All timestamps are stored with timezone=True so PostgreSQL persists them as
TIMESTAMPTZ (UTC).  Application code must always use UTC when creating
datetime objects.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.profile import Profile


# ── Role enum ─────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    """
    Inherits from `str` so the value is JSON-serialisable without extra
    conversion and works transparently with Pydantic schemas.
    """
    STUDENT    = "student"
    LECTURER   = "lecturer"
    COUNSELLOR = "counsellor"
    ADMIN      = "admin"


# ── Model ─────────────────────────────────────────────────────────────────────
class User(Base):
    """
    Central user account shared across all roles.

    Password storage
    ----------------
    Only the bcrypt hash is persisted.  The plain-text password is never
    stored or logged.

    UUID primary key
    ----------------
    Using UUID instead of an auto-increment integer prevents enumeration
    attacks and is required by the pseudonymisation layer (Feature 5).
    """

    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ── Authorisation ─────────────────────────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", create_type=True),
        nullable=False,
        default=UserRole.STUDENT,
        index=True,
    )

    # ── Status flags ──────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # ── UTC Timestamps ────────────────────────────────────────────────────────
    # server_default=func.now() lets PostgreSQL set the value so it is correct
    # even for bulk inserts that bypass the ORM layer.
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
    # uselist=False enforces 1-to-1 at the ORM level (DB uniqueness is on
    # profiles.user_id).  cascade="all, delete-orphan" ensures the profile row
    # is deleted when the user account is deleted.
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",   # always load explicitly with selectinload() in queries
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
