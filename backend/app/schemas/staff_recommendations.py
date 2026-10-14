"""
backend/app/schemas/staff_recommendations.py

Pydantic schemas for Feature 32: Staff Intervention Recommendation Panel (C4 FR5 / FR6).
Provides response models for recommendation triage list and ranked candidate inspection.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StaffRecommendationTopCandidate(BaseModel):
    """Summarized top-ranked intervention candidate for list view."""
    rank: int
    intervention_type: str
    label: str
    suitability_score: float


class StaffRecommendationListItem(BaseModel):
    """Overview item for recommendation triage list."""
    recommendation_id: str
    pid: str
    week_index: int
    status: str
    candidate_count: int
    top_candidate: Optional[StaffRecommendationTopCandidate] = None
    risk_tier: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None


class StaffRecommendationListResponse(BaseModel):
    """Paginated list response for staff recommendation triage."""
    items: List[StaffRecommendationListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class StaffRecommendationCandidateDetail(BaseModel):
    """Ranked candidate intervention evaluated by Component 4."""
    rank: int
    intervention_type: str
    label: str
    student_label: str
    delivery_module: str
    suitability_score: float
    rationale: str


class StaffRecommendationDetailResponse(BaseModel):
    """Comprehensive recommendation batch detail with ranked candidates and context link."""
    recommendation_id: str
    pid: str
    week_index: int
    status: str
    candidates: List[StaffRecommendationCandidateDetail]
    risk_tier: Optional[str] = None
    context_course_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
