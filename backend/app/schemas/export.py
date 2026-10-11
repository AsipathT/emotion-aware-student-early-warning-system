"""
backend/app/schemas/export.py

Feature 5: Safe Export Models.
Pydantic response models for component-facing and ML inference endpoints.
Strictly requires 'pid' and prohibits direct identifiers (student_id, name, email).
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class BaseSafeExportModel(BaseModel):
    """
    Base model for all sanitized, component-facing exports.
    Mandates pseudonym 'pid' and guarantees that personal identifiers
    (student_id, name, full_name, email) are never present.
    """
    pid: str = Field(
        ...,
        examples=["STU_a1b2c3d4"],
        description="Deterministic HMAC-SHA256 pseudonym identifier.",
    )

    model_config = {
        "from_attributes": True,
        "extra": "forbid",  # Rejects any unmodeled attributes to prevent accidental PII leakage
    }

    @model_validator(mode="before")
    @classmethod
    def verify_no_pii_keys(cls, data: object) -> object:
        """Strict guard ensuring prohibited PII fields are never passed."""
        forbidden_keys = {"student_id", "name", "full_name", "email", "hashed_password"}
        if isinstance(data, dict):
            found_forbidden = forbidden_keys.intersection(data.keys())
            if found_forbidden:
                # Strip out forbidden keys automatically if passing a raw user document
                cleaned = {k: v for k, v in data.items() if k not in forbidden_keys}
                return cleaned
        return data


class StudentSafeProfileExport(BaseSafeExportModel):
    """Sanitized student profile representation for analytics and ML pipeline."""
    role: str = "student"
    department: Optional[str] = None
    created_at: datetime
    is_active: bool = True


class EmotionLogExport(BaseSafeExportModel):
    """Sanitized facial/voice/text emotion telemetry record."""
    timestamp: datetime
    emotion: str = Field(..., description="Detected emotional state (e.g. engaged, frustrated, confused, bored)")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score from 0.0 to 1.0")
    valence: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Emotional positivity/negativity")
    arousal: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Emotional intensity/activation")
    module_id: Optional[str] = None


class EngagementMetricExport(BaseSafeExportModel):
    """Sanitized longitudinal engagement telemetry for dropout risk model."""
    course_id: str
    session_duration_minutes: float
    video_watch_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    quiz_score_average: Optional[float] = None
    forum_posts_count: int = 0
    assignments_submitted: int = 0
    timestamp: datetime


class DropoutRiskExport(BaseSafeExportModel):
    """Sanitized predictive risk output produced by early-warning classifier."""
    risk_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted dropout probability")
    risk_category: str = Field(..., description="Categorical risk rating: Low, Medium, High, or Critical")
    top_contributing_factors: List[str] = Field(default_factory=list, description="SHAP/LIME explanation features")
    recommended_action: Optional[str] = None
    calculated_at: datetime
