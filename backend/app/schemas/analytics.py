import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WeeklyFeatureResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    week_start: date
    session_frequency: int
    clicks_total: int
    active_days: int
    active_duration_trend: Optional[float] = None
    submission_delay_days: Optional[float] = None
    video_interaction_intensity: Optional[float] = None
    missed_assessments: int
    prev_attempts: int
    studied_credits: Optional[float] = None
    attendance_rate: Optional[float] = None
    score_so_far: Optional[float] = None
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskScoreResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    risk_score: float
    risk_tier: str
    calibrated: bool
    modality_weights: Optional[Dict[str, Any]] = None
    top_features: Optional[Dict[str, Any]] = None
    c1_snapshot: Optional[Dict[str, Any]] = None
    c2_snapshot: Optional[Dict[str, Any]] = None
    missing_modalities: Optional[Dict[str, Any]] = None
    schema_version: str
    model_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrajectoryLabelResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    label: str
    p_stable: Optional[float] = None
    p_improving: Optional[float] = None
    p_declining: Optional[float] = None
    p_volatile: Optional[float] = None
    confidence: Optional[float] = None
    indicators: Optional[Dict[str, Any]] = None
    schema_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AffectWeeklyCreate(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    exam_anxiety: Optional[float] = Field(None, ge=0.0, le=1.0)
    conceptual_confusion: Optional[float] = Field(None, ge=0.0, le=1.0)
    academic_helplessness: Optional[float] = Field(None, ge=0.0, le=1.0)
    course_frustration: Optional[float] = Field(None, ge=0.0, le=1.0)
    motivation_erosion: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    message_count: int = Field(default=0, ge=0)


class AffectWeeklyResponse(AffectWeeklyCreate):
    id: uuid.UUID
    schema_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkAffectWeeklyCreate(BaseModel):
    records: List[AffectWeeklyCreate]
