import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    pseudo_student_id: str
    course_id: uuid.UUID
    week_index: int
    exam_anxiety: Optional[float] = Field(None, ge=0.0, le=1.0)
    conceptual_confusion: Optional[float] = Field(None, ge=0.0, le=1.0)
    academic_helplessness: Optional[float] = Field(None, ge=0.0, le=1.0)
    course_frustration: Optional[float] = Field(None, ge=0.0, le=1.0)
    motivation_erosion: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    message_count: int = Field(default=0, ge=0)
    schema_version: str = "1.0"

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v not in ("1.0", "1"):
            raise ValueError("Unsupported schema_version. Expected '1.0'")
        return v


class AffectWeeklyResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    exam_anxiety: Optional[float] = None
    conceptual_confusion: Optional[float] = None
    academic_helplessness: Optional[float] = None
    course_frustration: Optional[float] = None
    motivation_erosion: Optional[float] = None
    confidence: Optional[float] = None
    message_count: int
    schema_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkAffectWeeklyCreate(BaseModel):
    records: List[AffectWeeklyCreate]


class RiskScoreCreate(BaseModel):
    pseudo_student_id: str
    course_id: uuid.UUID
    week_index: int
    risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_tier: str
    calibrated: bool = False
    modality_weights: Optional[Dict[str, float]] = None
    top_features: Optional[Dict[str, Any]] = None
    c1_snapshot: Optional[Dict[str, Any]] = None
    c2_snapshot: Optional[Dict[str, Any]] = None
    missing_modalities: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0"
    model_version: Optional[str] = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v not in ("1.0", "1"):
            raise ValueError("Unsupported schema_version. Expected '1.0'")
        return v

    @field_validator("risk_tier")
    @classmethod
    def validate_risk_tier(cls, v: str) -> str:
        valid_tiers = {"low", "medium", "high", "critical"}
        if v.lower() not in valid_tiers:
            raise ValueError(f"Invalid risk_tier: {v}. Must be one of Low, Medium, High, Critical")
        return v.capitalize()

    @field_validator("modality_weights")
    @classmethod
    def validate_modality_weights(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v is not None and len(v) > 0:
            total = sum(v.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(f"modality_weights must sum to 1.0 (got {total})")
        return v


class TrajectoryLabelCreate(BaseModel):
    pseudo_student_id: str
    course_id: uuid.UUID
    week_index: int
    label: str
    p_stable: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_improving: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_declining: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_volatile: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    indicators: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0"

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v not in ("1.0", "1"):
            raise ValueError("Unsupported schema_version. Expected '1.0'")
        return v

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        valid_labels = {"stable", "improving", "declining", "volatile"}
        if v.lower() not in valid_labels:
            raise ValueError(f"Invalid label: {v}. Must be one of Stable, Improving, Declining, Volatile")
        return v.capitalize()
