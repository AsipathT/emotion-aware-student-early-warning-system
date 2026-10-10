"""
backend/app/schemas/contract/v1/c1_affective.py

Contract schemas for Component 1: Affective State Detection.
- TextMessageRecord: Outbound from LMS to C1 (Feature 21). Scrubbed text only.
- AffectiveWeeklyVector: Inbound from C1 to LMS (Feature 23). Aggregated distress distribution.
"""

from typing import Dict, List, Optional
from pydantic import Field, field_validator

from app.schemas.contract.common import (
    CleanText,
    ContractBaseModel,
    CourseId,
    DistressClass,
    Pid,
    Score01,
    SourceType,
    UtcDatetime,
    WeekIndex,
)


class TextMessageRecord(ContractBaseModel):
    """
    Individual text interaction message extracted from LMS discussion forums,
    course chats, or reflective learning journals.
    Transmitted from LMS to Component 1 (Affective State Detection).
    Strictly redacted: raw_text and identifying tokens are prohibited.
    """
    message_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier of the communication item within LMS",
    )
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    course_id: CourseId = Field(
        ...,
        description="Course institutional identifier (e.g. CS101)",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week in which message was submitted",
    )
    source_type: SourceType = Field(
        ...,
        description="Communication medium (forum, chat, or journal)",
    )
    clean_text: CleanText = Field(
        ...,
        min_length=1,
        description="Scrubbed and de-identified text payload (free of names, emails, reg IDs)",
    )
    timestamp: UtcDatetime = Field(
        ...,
        description="UTC timestamp when the student posted the message",
    )
    response_latency_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Elapsed seconds before a reply/post was made, if applicable",
    )
    message_length_chars: int = Field(
        ...,
        ge=0,
        description="Character count of the scrubbed message text",
    )
    message_length_words: int = Field(
        ...,
        ge=0,
        description="Word count of the scrubbed message text",
    )
    reply_to_id: Optional[str] = Field(
        default=None,
        description="Message ID this post replies to, if part of a thread",
    )


class TopDriver(ContractBaseModel):
    """Token, n-gram, or linguistic marker driving an affective classification."""
    token_or_marker: CleanText = Field(
        ...,
        description="Linguistic feature or key marker token explaining distress",
    )
    weight: float = Field(
        ...,
        description="Model attribution or attention weight associated with this driver",
    )


class AffectiveWeeklyVector(ContractBaseModel):
    """
    Aggregated affective distress distribution and stress indicators for a student
    over a one-week observation window.
    Transmitted from Component 1 to the LMS database (Feature 23).
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
    emotion_scores: Dict[DistressClass, Score01] = Field(
        ...,
        description="Probability distribution across all 5 DistressClass categories (all keys mandatory)",
    )
    stress_label: CleanText = Field(
        ...,
        description="Dominant or summary stress category designation",
    )
    confidence: Score01 = Field(
        ...,
        description="Model prediction confidence score between 0.0 and 1.0",
    )
    message_count: int = Field(
        ...,
        ge=0,
        description="Total volume of text messages analyzed during this weekly window",
    )
    top_drivers: List[TopDriver] = Field(
        default_factory=list,
        max_length=10,
        description="Top explanatory markers or keywords (maximum 10)",
    )

    @field_validator("emotion_scores")
    @classmethod
    def validate_all_emotions_present(
        cls, v: Dict[DistressClass, float]
    ) -> Dict[DistressClass, float]:
        missing = set(DistressClass) - set(v.keys())
        if missing:
            missing_names = sorted([m.value for m in missing])
            raise ValueError(
                f"emotion_scores must contain all 5 DistressClass keys. Missing: {missing_names}"
            )
        return v
