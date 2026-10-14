"""
backend/app/schemas/staff_students.py

Pydantic schemas for Feature 31: Staff Student Context & Unified Analytics (C4 Input).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StaffStudentOverviewItem(BaseModel):
    """Overview item for student triage list combining C1, C2, and C3 indicators."""
    pid: str
    course_id: str
    week_index: int
    risk_score: Optional[float] = None
    risk_tier: str
    trajectory_label: str
    dominant_distress_class: str


class StaffStudentOverviewResponse(BaseModel):
    """Paginated list response for staff student risk overview."""
    items: List[StaffStudentOverviewItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class StudentContextIdentity(BaseModel):
    pid: str


class StudentContextC1(BaseModel):
    latest: Optional[Dict[str, Any]] = None
    change_vs_previous: Dict[str, float] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextC2(BaseModel):
    latest: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextC3(BaseModel):
    latest: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextBehaviour(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextInterventions(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextFreshness(BaseModel):
    c1_week: Optional[int] = None
    c2_week: Optional[int] = None
    c3_week: Optional[int] = None
    behaviour_week: Optional[int] = None
    max_observed_week: int = 0
    lagging_sources: List[Dict[str, Any]] = Field(default_factory=list)


class StudentContextResponse(BaseModel):
    """Comprehensive synthesized context payload for Component 4."""
    identity: StudentContextIdentity
    c1: StudentContextC1
    c2: StudentContextC2
    c3: StudentContextC3
    behaviour: StudentContextBehaviour
    interventions: StudentContextInterventions
    latest_common_week: int
    data_freshness: StudentContextFreshness
    summary_lines: List[str]
