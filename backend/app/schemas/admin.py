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


# ── Phase 2: Course Administration ───────────────────────────────────────────

class AdminCourseSummary(BaseModel):
    """Course item representation in the Admin Panel."""

    id: str
    course_id: str
    title: str
    description: Optional[str] = None
    lecturer_id: Optional[str] = None
    lecturer_name: Optional[str] = None
    lecturer_email: Optional[str] = None
    is_published: bool = True
    enrolment_count: int = 0
    module_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminPaginatedCoursesResponse(BaseModel):
    """Paginated list of courses with admin metadata."""

    items: List[AdminCourseSummary] = Field(default_factory=list)
    total: int = Field(..., description="Total matching courses.")
    page: int = Field(..., description="Current 1-based page number.")
    page_size: int = Field(..., description="Items per page.")
    total_pages: int = Field(..., description="Total available pages.")


class AdminCoursePublishUpdate(BaseModel):
    """Payload to publish or unpublish a course."""

    is_published: bool = Field(..., description="True to publish to catalog, False to unpublish.")


class AdminCourseLecturerUpdate(BaseModel):
    """Payload to assign or reassign the instructor of a course."""

    lecturer_id: str = Field(..., description="User ID of the assigned instructor.")


# ── Phase 2: Enrolment Administration ─────────────────────────────────────────

class AdminEnrolmentItem(BaseModel):
    """Enrolment record enriched with course and student metadata."""

    id: str
    course_id: str
    course_title: Optional[str] = None
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    pid: Optional[str] = None
    status: str = "active"  # "active" | "dropped"
    enrolled_at: Optional[datetime] = None
    enrolment_end: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminPaginatedEnrolmentsResponse(BaseModel):
    """Paginated list of student course enrolments."""

    items: List[AdminEnrolmentItem] = Field(default_factory=list)
    total: int = Field(..., description="Total matching enrolment records.")
    page: int = Field(..., description="Current 1-based page number.")
    page_size: int = Field(..., description="Items per page.")
    total_pages: int = Field(..., description="Total available pages.")


class AdminEnrolmentCreateRequest(BaseModel):
    """Payload to manually enrol a single student into a course."""

    course_id: str = Field(..., description="Course ID or identifier.")
    student_identifier: str = Field(..., description="Student email, UUID, or PID.")


class BulkEnrolmentRowResult(BaseModel):
    """Result for an individual student in a bulk enrolment batch."""

    identifier: str
    status: str  # "enrolled" | "skipped" | "failed"
    reason: Optional[str] = None
    student_id: Optional[str] = None
    pid: Optional[str] = None


class AdminBulkEnrolmentRequest(BaseModel):
    """Payload to bulk enrol students into a course."""

    course_id: str = Field(..., description="Target course ID.")
    student_identifiers: List[str] = Field(..., min_length=1, description="List of emails, user IDs, or PIDs.")


class AdminBulkEnrolmentResponse(BaseModel):
    """Summary and row-by-row breakdown of a bulk enrolment action."""

    course_id: str
    total: int
    enrolled_count: int
    skipped_count: int
    failed_count: int
    results: List[BulkEnrolmentRowResult] = Field(default_factory=list)


# ── Phase 2: Consent & Ethics Governance ──────────────────────────────────────

class AdminCourseConsentBreakdown(BaseModel):
    """Course-level consent metrics."""

    course_id: str
    course_title: str
    enrolled_students: int
    accepted: int
    withdrawn: int
    declined: int
    pending: int
    coverage_percentage: float


class AdminConsentNoticeHistoryItem(BaseModel):
    """Historical or active consent notice version."""

    id: str
    version: int
    text: str
    effective_from: datetime
    is_active: bool


class AdminConsentCoverageResponse(BaseModel):
    """System-wide and course-level consent posture for the active notice."""

    active_notice: Optional[Dict[str, Any]] = None
    active_version: Optional[int] = None
    total_students: int
    accepted: int
    withdrawn: int
    declined: int
    pending: int
    coverage_percentage: float
    course_breakdown: List[AdminCourseConsentBreakdown] = Field(default_factory=list)
    notice_history: List[AdminConsentNoticeHistoryItem] = Field(default_factory=list)


# ── Phase 3: Ingestion Health & Runs ──────────────────────────────────────────

class ComponentIngestionHealth(BaseModel):
    """Health metrics and configuration status for an individual ML component."""

    component: str  # "c1", "c2", "c3", "c4"
    title: str
    api_key_configured: bool = Field(..., description="True if component API key is set; NEVER exposes key.")
    status: str = "idle"  # "success" | "partial" | "failed" | "idle"
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    contract_version: Optional[str] = "1.0.0"
    records_accepted_total: int = 0
    records_rejected_total: int = 0
    records_processed_total: int = 0


class AdminIngestionStatusResponse(BaseModel):
    """Platform-wide ingestion status across all 4 ML components."""

    components: Dict[str, ComponentIngestionHealth] = Field(default_factory=dict)
    total_runs: int = 0
    active_runs: int = 0


class AdminIngestionRunItem(BaseModel):
    """Detailed record of a component ingestion run."""

    id: str
    component: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str  # "success" | "partial" | "failed"
    records_processed: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    dry_run: bool = False
    contract_version: Optional[str] = None
    error_message: Optional[str] = None


class AdminPaginatedIngestionRunsResponse(BaseModel):
    """Paginated list of historical component ingestion runs."""

    items: List[AdminIngestionRunItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Phase 3: Privacy & Identity Reveal ────────────────────────────────────────

class AdminIdentityRevealRequest(BaseModel):
    """Break-glass student identity reveal request."""

    pid: str = Field(..., description="Student Pseudonym ID, e.g. STU_a1b2c3d4")
    justification: str = Field(
        ...,
        min_length=10,
        description="Mandatory justification reason for identity reveal (minimum 10 characters).",
    )


class AdminIdentityRevealResponse(BaseModel):
    """Transient identity reveal response (never cached or logged)."""

    pid: str
    student_id: str
    name: str
    email: str


class AdminRevealHistoryItem(BaseModel):
    """Historical identity reveal audit record."""

    id: str
    timestamp: datetime
    actor_id: str
    actor_role: str
    pid: str
    reason: str
    outcome: str


class AdminPaginatedRevealHistoryResponse(BaseModel):
    """Paginated identity reveal audit logs."""

    items: List[AdminRevealHistoryItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminScrubTestRequest(BaseModel):
    """Payload for interactive PII scrub tester sandbox."""

    text: str = Field(..., description="Free text containing potential PII.")
    known_names: Optional[List[str]] = Field(default=None, description="Optional names to redact.")


class AdminScrubTestResponse(BaseModel):
    """Sanitized text output and redaction breakdown."""

    clean_text: str
    redaction_report: Dict[str, int]


# ── Phase 3: Exports & History ────────────────────────────────────────────────

class AdminExportHistoryItem(BaseModel):
    """Historical data export audit event."""

    id: str
    timestamp: datetime
    actor_id: str
    actor_role: str
    dataset: str
    format: str
    row_count: int
    filters: Dict[str, Any] = Field(default_factory=dict)


class AdminPaginatedExportHistoryResponse(BaseModel):
    """Paginated export audit events."""

    items: List[AdminExportHistoryItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Phase 3: System Diagnostics & Health ──────────────────────────────────────

class AdminMigrationItem(BaseModel):
    """Applied schema migration record."""

    migration_id: str
    applied_at: datetime


class AdminSystemHealthResponse(BaseModel):
    """System health diagnostics, database latency, contract schemas, and migrations."""

    status: str
    db_status: str
    db_ping_ms: float
    contract_version: str
    contract_schemas: List[str] = Field(default_factory=list)
    applied_migrations: List[AdminMigrationItem] = Field(default_factory=list)
    total_migrations_applied: int
    oulad_status: Dict[str, Any] = Field(default_factory=dict)


