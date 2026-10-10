"""
backend/app/schemas/contract/v1/c3_risk.py

Contract schemas for Component 3: Multimodal Risk Prediction.
- AcademicRecord: Outbound from LMS to C3 (Feature 21). Grades, attendance, milestone marks.
- RiskAssessment: Inbound from C3 to LMS (Feature 23). Unified risk score, tier, and modality breakdown.
"""

from typing import List, Optional
from pydantic import Field, model_validator

from app.schemas.contract.common import (
    CleanText,
    ContractBaseModel,
    CourseId,
    Pid,
    RiskTier,
    Score01,
    WeekIndex,
)


class AcademicRecord(ContractBaseModel):
    """
    Weekly academic performance, milestone grades, and attendance metrics.
    Transmitted from LMS to Component 3 (Multimodal Risk Prediction).
    """
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    course_id: CourseId = Field(
        ...,
        description="Course institutional identifier",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week of assessment",
    )
    ca_marks: Optional[float] = Field(
        default=None,
        description="Continuous assessment cumulative marks recorded so far",
    )
    midterm_mark: Optional[float] = Field(
        default=None,
        description="Midterm examination score if completed in this or prior weeks",
    )
    quiz_scores: List[float] = Field(
        default_factory=list,
        description="Individual quiz percentage or point scores recorded in this week",
    )
    attendance_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Cumulative attendance percentage to date (0.0 to 100.0)",
    )
    submission_delay_hours: float = Field(
        ...,
        description="Academic assignment deadline offset (negative = early, positive = late)",
    )


class ModalityContributions(ContractBaseModel):
    """
    Normalized proportional contribution of each data modality to the overall risk prediction.
    Must sum to 1.0 within a floating-point tolerance of 0.01.
    """
    affective: Score01 = Field(
        ...,
        description="Proportion of risk attributed to affective / distress signals (0.0 - 1.0)",
    )
    behavioral: Score01 = Field(
        ...,
        description="Proportion of risk attributed to engagement & LMS clickstream signals (0.0 - 1.0)",
    )
    academic: Score01 = Field(
        ...,
        description="Proportion of risk attributed to academic performance & attendance (0.0 - 1.0)",
    )

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> "ModalityContributions":
        total = self.affective + self.behavioral + self.academic
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Modality contributions must sum to 1.0 (within tolerance 0.01). "
                f"Computed sum: {total:.4f} (affective={self.affective}, "
                f"behavioral={self.behavioral}, academic={self.academic})."
            )
        return self


class RiskAssessment(ContractBaseModel):
    """
    Multimodal student dropout or disengagement risk assessment.
    Combines affective, behavioral, and academic dimensions.
    Transmitted from Component 3 to LMS database (Feature 23).
    """
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    course_id: CourseId = Field(
        ...,
        description="Course institutional identifier",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week of evaluation",
    )
    risk_score: Score01 = Field(
        ...,
        description="Comprehensive composite risk probability score (0.0 to 1.0)",
    )
    risk_tier: RiskTier = Field(
        ...,
        description="Categorical risk classification (low, medium, high, critical)",
    )
    modality_contributions: ModalityContributions = Field(
        ...,
        description="Proportional attribution across affective, behavioral, and academic sources",
    )
    top_drivers: List[CleanText] = Field(
        default_factory=list,
        max_length=10,
        description="Key risk factors and multimodal indicators (maximum 10)",
    )
