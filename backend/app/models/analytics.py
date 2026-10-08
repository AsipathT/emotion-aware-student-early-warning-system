import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WeeklyFeature(Base):
    __tablename__ = "weekly_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    week_index: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    
    session_frequency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_duration_trend: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submission_delay_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_interaction_intensity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    missed_assessments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prev_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    studied_credits: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attendance_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_so_far: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "week_index", name="uix_weekly_features_student_course_week"),
    )


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    week_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    calibrated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    modality_weights: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    top_features: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    c1_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    c2_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    missing_modalities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "week_index", name="uix_risk_scores_student_course_week"),
    )


class TrajectoryLabel(Base):
    __tablename__ = "trajectory_labels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    week_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    p_stable: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_improving: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_declining: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_volatile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    indicators: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "week_index", name="uix_trajectory_labels_student_course_week"),
    )


class SyntheticGroundTruth(Base):
    __tablename__ = "synthetic_ground_truth"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    planted_driver: Mapped[str] = mapped_column(String(50), nullable=False)
    onset_week: Mapped[int] = mapped_column(Integer, nullable=False)
    withdrawal_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AffectWeekly(Base):
    __tablename__ = "affect_weekly"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    week_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    exam_anxiety: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conceptual_confusion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    academic_helplessness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    course_frustration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    motivation_erosion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "week_index", name="uix_affect_weekly_student_course_week"),
    )
