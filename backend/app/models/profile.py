"""
backend/app/models/profile.py

SQLAlchemy 2.0 Profile model — a strict 1-to-1 extension of User.

Design decisions
----------------
* Separate table (not columns on `users`) keeps the User model lean and allows
  the profile to be lazily loaded only when needed.
* `user_id` has a UNIQUE constraint enforcing the 1-to-1 cardinality at the
  database level, independent of the ORM relationship.
* All timestamps use `DateTime(timezone=True)` → PostgreSQL TIMESTAMPTZ (UTC).
* `student_id` is nullable because lecturers, counsellors and admins do not
  carry a student registration number.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Profile(Base):
    """
    Extended profile record for every registered user.

    A profile row is created automatically on the first PUT /users/me/profile
    request (upsert pattern) so it is never missing from the database.
    """

    __tablename__ = "profiles"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── FK → users (1-to-1, enforced at DB level by UNIQUE) ──────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,        # ← DB-level 1-to-1 enforcement
        nullable=False,
        index=True,
    )

    # ── Profile fields (all nullable — filled in progressively) ───────────────
    student_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,        # no two users may share a student registration number
        index=True,
        comment="Institutional student registration / matriculation number.",
    )
    department: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Faculty or department name.",
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short self-description written by the user.",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Absolute URL to the user's avatar image.",
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

    # ── Back-reference to User (populated by User.profile relationship) ───────
    user: Mapped["app.models.user.User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="profile",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Profile user_id={self.user_id} student_id={self.student_id!r}>"
