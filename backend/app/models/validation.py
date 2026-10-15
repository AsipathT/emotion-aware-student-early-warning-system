"""
backend/app/models/validation.py

Feature 36: Ground-truth validation models for Component 1 (Affective Distress Confirmation)
and Component 4 (Recommendation Appropriateness & Ranking Evaluation).
Defines operational collections `validation_labels` and `recommendation_ratings`.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

COL_VALIDATION_LABELS = "validation_labels"
COL_RECOMMENDATION_RATINGS = "recommendation_ratings"

C1DistressLabel = Literal[
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "none",
]


class ValidationLabel(BaseModel):
    """
    Expert counsellor ground-truth confirmation on a student's weekly affective state.
    Used for inter-rater agreement (Cohen's kappa) and model macro-F1 evaluation.
    """
    label_id: str = Field(..., description="Unique UUID for this validation label")
    kind: Literal["c1_distress"] = "c1_distress"
    pid: str = Field(..., description="Pseudonymized student identifier (STU_xxxxxxxx)")
    course_id: str = Field(..., description="Course identifier")
    week_index: int = Field(..., ge=0, description="Academic week index")
    model_top_class: str = Field(..., description="Model dominant distress class")
    model_top_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    counsellor_label: C1DistressLabel = Field(..., description="Human expert confirmed label")
    confidence: int = Field(..., ge=1, le=3, description="Counsellor rating confidence (1=Low, 2=Medium, 3=High)")
    reviewer_id: str = Field(..., description="User ID of the reviewing counsellor")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of label submission",
    )

    model_config = {
        "from_attributes": True,
    }


class RecommendationRating(BaseModel):
    """
    Expert appropriateness rating and candidate rank suitability evaluation for Component 4.
    Used for ranking evaluation metrics (Precision@K, NDCG@K).
    """
    id: str = Field(..., description="Unique rating identifier")
    recommendation_id: str = Field(..., description="Target recommendation UUID")
    reviewer_id: str = Field(..., description="User ID of the reviewing counsellor")
    appropriateness: int = Field(..., ge=1, le=5, description="1-5 Likert appropriateness rating")
    suitable_ranks: List[int] = Field(
        default_factory=list,
        description="List of candidate ranks deemed clinically suitable (e.g. [1, 3])",
    )
    top1_acceptable: bool = Field(
        ...,
        description="Whether the top-ranked recommendation is clinically acceptable as primary action",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Private feedback note by reviewer, excluded from exports",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of rating submission",
    )

    model_config = {
        "from_attributes": True,
    }
