import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class WeeklyFeature(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    week_start: date
    session_frequency: int = 0
    clicks_total: int = 0
    active_days: int = 0
    active_duration_trend: Optional[float] = None
    submission_delay_days: Optional[float] = None
    video_interaction_intensity: Optional[float] = None
    missed_assessments: int = 0
    prev_attempts: int = 0
    studied_credits: Optional[float] = None
    attendance_rate: Optional[float] = None
    score_so_far: Optional[float] = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["student_id"] = str(d["student_id"])
        d["course_id"] = str(d["course_id"])
        d["week_start"] = datetime.combine(d["week_start"], datetime.min.time(), tzinfo=timezone.utc)
        return d


class RiskScore(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    risk_score: float
    risk_tier: str
    calibrated: bool = False
    modality_weights: Optional[Dict[str, Any]] = None
    top_features: Optional[Dict[str, Any]] = None
    c1_snapshot: Optional[Dict[str, Any]] = None
    c2_snapshot: Optional[Dict[str, Any]] = None
    missing_modalities: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0"
    model_version: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["student_id"] = str(d["student_id"])
        d["course_id"] = str(d["course_id"])
        return d


class TrajectoryLabel(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
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
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["student_id"] = str(d["student_id"])
        d["course_id"] = str(d["course_id"])
        return d


class AffectWeekly(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    student_id: uuid.UUID
    course_id: uuid.UUID
    week_index: int
    exam_anxiety: Optional[float] = None
    conceptual_confusion: Optional[float] = None
    academic_helplessness: Optional[float] = None
    course_frustration: Optional[float] = None
    motivation_erosion: Optional[float] = None
    confidence: Optional[float] = None
    message_count: int = 0
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["student_id"] = str(d["student_id"])
        d["course_id"] = str(d["course_id"])
        return d
