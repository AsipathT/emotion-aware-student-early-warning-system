"""
backend/app/schemas/staff_interventions.py

Pydantic schemas for Feature 34: Staff Intervention Management (C4 FR10).
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class StaffMemberItem(BaseModel):
    """Staff member profile for assignment dropdown."""
    id: str
    full_name: str
    role: str


class StaffInterventionListItem(BaseModel):
    """Summary item for staff intervention management table."""
    id: str
    recommendation_id: Optional[str] = None
    origin: str
    pid: str
    course_id: str
    intervention_type: str
    label: str
    student_label: str
    delivery_module: str
    status: str
    created_by: str
    assigned_to: Optional[str] = None
    assigned_staff_name: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class StaffInterventionListResponse(BaseModel):
    """Paginated response for intervention list."""
    items: List[StaffInterventionListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class StaffInterventionNoteItem(BaseModel):
    """Immutable counselor case note."""
    note_id: str
    author_id: str
    author_role: str
    content: str
    created_at: datetime


class StaffInterventionDetailResponse(BaseModel):
    """Full operational intervention record detail."""
    id: str
    recommendation_id: Optional[str] = None
    origin: str
    pid: str
    course_id: str
    intervention_type: str
    label: str
    student_label: str
    delivery_module: str
    description: str
    status: str
    created_by: str
    assigned_to: Optional[str] = None
    assigned_staff_name: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    baseline_snapshot: Dict[str, Any]
    status_history: List[Dict[str, Any]]
    notes: List[StaffInterventionNoteItem]
    created_at: datetime
    updated_at: datetime


class ManualInterventionCreateRequest(BaseModel):
    """Request payload for counselor-initiated manual intervention."""
    pid: str = Field(..., min_length=1, description="Pseudonymized student identifier (STU_...)")
    course_id: str = Field(..., min_length=1, description="Target course identifier")
    intervention_type: str = Field(..., min_length=1, description="Catalog intervention type key")
    reason: str = Field(..., min_length=10, max_length=500, description="Clinical or academic rationale (10-500 chars)")


class StaffInterventionPatchRequest(BaseModel):
    """Request payload for updating assignment, schedule, or advancing lifecycle."""
    assigned_to: Optional[str] = Field(default=None, description="User ID of assigned active staff member")
    scheduled_for: Optional[datetime] = Field(default=None, description="Scheduled session datetime (must not be past)")
    status: Optional[str] = Field(default=None, description="Target lifecycle state (offered, in_progress, cancelled)")
    note: Optional[str] = Field(default=None, max_length=500, description="Optional transition note")


class StaffInterventionNoteCreateRequest(BaseModel):
    """Request payload for appending a private counselor note."""
    content: str = Field(..., min_length=1, max_length=2000, description="Private case note text (1-2000 chars)")


class StaffInterventionNoteCreateResponse(BaseModel):
    """Response returned upon appending note."""
    note: StaffInterventionNoteItem
    total_notes: int
