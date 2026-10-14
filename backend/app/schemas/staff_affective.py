"""
backend/app/schemas/staff_affective.py

Pydantic schemas for Feature 30: Staff Affective Analytics & Explainability (C1).
All schemas enforce strict typing, UTC datetimes, and forbidden PII denylists.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HighlightedSegment(BaseModel):
    """Segment of scrubbed text with an optional attention / SHAP attribution weight."""
    text: str
    weight: Optional[float] = None


class StaffStudentSummaryItem(BaseModel):
    """Summary of a student's latest or specific week affective distress status."""
    pid: str
    course_id: str
    week_index: int
    dominant_class: str
    dominant_score: float
    stress_label: str
    confidence: float
    message_count: int


class StaffStudentListResponse(BaseModel):
    """Paginated list response for staff student overview."""
    items: List[StaffStudentSummaryItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class TopDriverItem(BaseModel):
    """Linguistic marker token with model attribution weight."""
    token_or_marker: str
    weight: float


class StaffAffectiveHistoryItem(BaseModel):
    """Single-week longitudinal observation of affective scores with rationale."""
    week_index: int
    emotion_scores: Dict[str, float]
    stress_label: str
    confidence: float
    message_count: int
    top_drivers: List[TopDriverItem] = Field(default_factory=list)
    dominant_class: str
    dominant_score: float
    rationale: str


class StaffAffectiveHistoryResponse(BaseModel):
    """Longitudinal trajectory of a student's affective state across weeks."""
    pid: str
    course_id: str
    history: List[StaffAffectiveHistoryItem]


class StaffScrubbedMessageItem(BaseModel):
    """De-identified student message with highlighted linguistic markers."""
    message_id: str
    source_type: str
    timestamp: datetime
    segments: List[HighlightedSegment]
