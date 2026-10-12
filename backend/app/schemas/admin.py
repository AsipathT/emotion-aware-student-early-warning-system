"""
backend/app/schemas/admin.py

Pydantic v2 schemas for the Admin Panel (Feature 40).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.profile import ProfileResponse


# ── Statistics and Overview ───────────────────────────────────────────────────

class SystemStatsResponse(BaseModel):
    """System-wide metrics and resource counts for the Admin Panel."""

    total_users: int = Field(..., description="Total registered user accounts across all roles.")
    active_users: int = Field(..., description="Count of currently active (non-suspended) users.")
    total_courses: int = Field(..., description="Total academic courses registered on the platform.")
    published_courses: int = Field(..., description="Count of published and catalog-visible courses.")
    total_students: int = Field(default=0, description="Count of student accounts.")
    total_lecturers: int = Field(default=0, description="Count of lecturer/instructor accounts.")


class AdminOverviewResponse(BaseModel):
    """Consolidated platform-wide metrics and operational health for the Admin Panel."""

    total_users: int = Field(..., description="Total registered user accounts across all roles.")
    active_users: int = Field(..., description="Count of active user accounts.")
    suspended_users: int = Field(default=0, description="Count of suspended user accounts.")
    users_by_role: Dict[str, int] = Field(default_factory=dict, description="Account distribution by role.")
    total_courses: int = Field(..., description="Total courses in system.")
    published_courses: int = Field(..., description="Total published courses.")
    draft_courses: int = Field(default=0, description="Total unpublished/draft courses.")
    total_enrolments: int = Field(default=0, description="Total active course enrolments.")
    consent_coverage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Consent statistics (accepted, pending, withdrawn counts and percentage).",
    )
    pipeline_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline health summary (latest run status, stage completion, scheduler state).",
    )
    ingestion_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Ingestion status per ML component (C1-C4 latest run, accepted/rejected).",
    )
    recent_audit_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Last 10 security and platform audit events.",
    )
    database_health: Dict[str, Any] = Field(
        default_factory=dict,
        description="Database connectivity and round-trip ping time in ms.",
    )


# ── User Administration ───────────────────────────────────────────────────────

class UserStatusUpdate(BaseModel):
    """Payload to activate or suspend a specific user account."""

    is_active: bool = Field(..., description="True to activate account; False to suspend.")


class UserRoleUpdate(BaseModel):
    """Payload to update a user's authorization role."""

    role: UserRole = Field(..., description="New role assigned to the user.")


class AdminUserCreateRequest(BaseModel):
    """Payload for administrators to provision a new user account."""

    email: EmailStr = Field(..., description="Unique email address for authentication.")
    full_name: str = Field(..., min_length=2, max_length=120, description="Full legal or display name.")
    password: str = Field(..., min_length=8, description="Initial or temporary account password.")
    role: UserRole = Field(default=UserRole.STUDENT, description="Assigned platform role.")
    phone: Optional[str] = Field(default=None, max_length=30, description="Contact telephone number.")
    bio: Optional[str] = Field(default=None, max_length=500, description="User biography summary.")
    department: Optional[str] = Field(default=None, max_length=120, description="Academic department or faculty.")


class AdminUserUpdateRequest(BaseModel):
    """Payload to update editable profile fields of a user."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    bio: Optional[str] = Field(default=None, max_length=500)
    department: Optional[str] = Field(default=None, max_length=120)


class AdminProfileResponse(BaseModel):
    id: Optional[Union[uuid.UUID, str]] = None
    user_id: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True, "extra": "ignore"}


class AdminUserResponse(BaseModel):
    """Administrative representation of a user account with nested profile."""

    id: Union[uuid.UUID, str]
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    pid: Optional[str] = Field(default=None, description="Feature 5 pseudonym ID for students.")
    profile: Optional[Union[AdminProfileResponse, Dict[str, Any]]] = None

    model_config = {"from_attributes": True}


class AdminPaginatedUsersResponse(BaseModel):
    """Paginated user listing with navigation metadata."""

    items: List[AdminUserResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching accounts.")
    page: int = Field(..., description="Current 1-based page number.")
    page_size: int = Field(..., description="Items per page.")
    total_pages: int = Field(..., description="Total available pages.")


class AdminEnrolmentSummary(BaseModel):
    """Compact summary of a user's course enrolment."""

    course_id: str
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    status: str = "active"


class AdminConsentSummary(BaseModel):
    """Summary of student consent posture."""

    has_decision: bool = False
    decision: Optional[str] = None  # accepted, declined, withdrawn
    decided_at: Optional[datetime] = None
    notice_version: Optional[str] = None


class AdminUserDetailResponse(BaseModel):
    """Comprehensive user detail drawer data."""

    id: Union[uuid.UUID, str]
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    pid: Optional[str] = None
    profile: Optional[Union[AdminProfileResponse, Dict[str, Any]]] = None
    enrolments: List[AdminEnrolmentSummary] = Field(default_factory=list)
    consent: Optional[AdminConsentSummary] = None

    model_config = {"from_attributes": True}
