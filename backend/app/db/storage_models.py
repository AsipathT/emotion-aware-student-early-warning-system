"""
backend/app/db/storage_models.py

Feature 25: Pydantic MongoDB Storage Models.
Extends Feature 24 Contract Models with database persistence envelopes:
- _id (MongoDB primary identifier)
- schema_version (int: storage document version, distinct from semantic contract version)
- ingested_at (UTC-aware timestamp when document was persisted)
- source_version (str: semantic version of the originating payload, e.g. "1.0")

Weekly collections explicitly mandate: _id, schema_version, pid, course_id, week_index.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contract.common import (
    CleanText,
    CourseId,
    Decision,
    DistressClass,
    Pid,
    RiskTier,
    Score01,
    SourceType,
    TrajectoryLabel,
    UtcDatetime,
    WeekIndex,
)
from app.schemas.contract.v1 import (
    AcademicRecord,
    AffectiveWeeklyVector,
    BehaviorWeeklyRecord,
    EngagementTrajectory,
    InterventionCandidate,
    InterventionOutcome,
    InterventionRecommendation,
    ModalityContributions,
    RiskAssessment,
    TextMessageRecord,
    TopDriver,
)


# ── Base Storage Documents ────────────────────────────────────────────────────

class StorageDocument(BaseModel):
    """Base model for all MongoDB stored documents."""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        alias="_id",
        description="MongoDB unique primary key identifier",
    )
    schema_version: int = Field(
        default=1,
        ge=1,
        description="Database storage document schema version (distinct from contract version)",
    )
    ingested_at: UtcDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp recording when document was written to database",
    )
    source_version: str = Field(
        default="1.0",
        description="Contract specification version of incoming data payload",
    )
    source: Optional[str] = Field(
        default=None,
        description="Data origin provenance, e.g. 'oulad' or 'synthetic'",
    )
    ingestion_run_id: Optional[str] = Field(
        default=None,
        description="Identifier of ingestion batch run",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class LegacyIdStorageDocument(StorageDocument):
    """Storage base for collections whose routers still write a duplicate 'id' next to '_id'.

    Temporary: remove once the routers stop writing 'id' and use '_id' only.
    """
    legacy_id: Optional[str] = Field(
        default=None,
        alias="id",
        description="Deprecated duplicate of _id",
    )


class WeeklyStorageDocument(StorageDocument):
    """Base storage model for all weekly time-windowed student records."""
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
        description="Zero-indexed academic week of observation",
    )


# ── Contract Storage Extensions (Feature 24 Models) ───────────────────────────

class TextMessageStorage(StorageDocument):
    """Storage model for messages collection (LMS -> C1)."""
    message_id: str = Field(..., min_length=1)
    pid: Pid
    course_id: CourseId
    week_index: WeekIndex
    source_type: SourceType
    clean_text: CleanText
    timestamp: UtcDatetime
    response_latency_seconds: Optional[float] = Field(default=None, ge=0.0)
    message_length_chars: int = Field(..., ge=0)
    message_length_words: int = Field(..., ge=0)
    reply_to_id: Optional[str] = None


class BehaviorWeeklyStorage(WeeklyStorageDocument):
    """Storage model for behavior_weekly collection (LMS -> C2)."""
    login_count: int = Field(..., ge=0)
    session_minutes: float = Field(..., ge=0.0)
    clicks: int = Field(..., ge=0)
    video_play_count: int = Field(..., ge=0)
    video_pause_count: int = Field(..., ge=0)
    video_rewind_count: int = Field(..., ge=0)
    video_skip_count: int = Field(..., ge=0)
    video_completion_pct: float = Field(..., ge=0.0, le=100.0)
    submissions_count: int = Field(..., ge=0)
    avg_submission_delay_hours: float


class AcademicRecordStorage(WeeklyStorageDocument):
    """Storage model for academic_records / C3 outbound."""
    ca_marks: Optional[float] = None
    midterm_mark: Optional[float] = None
    quiz_scores: List[float] = Field(default_factory=list)
    attendance_pct: float = Field(..., ge=0.0, le=100.0)
    submission_delay_hours: float


class AffectiveWeeklyStorage(WeeklyStorageDocument):
    """Storage model for affective_weekly collection (C1 -> LMS)."""
    emotion_scores: Dict[DistressClass, Score01]
    stress_label: CleanText
    confidence: Score01
    message_count: int = Field(..., ge=0)
    top_drivers: List[TopDriver] = Field(default_factory=list, max_length=10)


class EngagementTrajectoryStorage(WeeklyStorageDocument):
    """Storage model for engagement_trajectories collection (C2 -> LMS)."""
    trajectory_label: TrajectoryLabel
    confidence: Score01
    contributing_indicators: List[CleanText] = Field(default_factory=list, max_length=10)


class RiskAssessmentStorage(WeeklyStorageDocument):
    """Storage model for risk_assessments collection (C3 -> LMS)."""
    risk_score: Score01
    risk_tier: RiskTier
    modality_contributions: ModalityContributions
    top_drivers: List[CleanText] = Field(default_factory=list, max_length=10)


class RecommendationStorage(StorageDocument):
    """Storage model for recommendations collection (C4 -> LMS)."""
    recommendation_id: str = Field(..., min_length=1)
    pid: Pid
    week_index: WeekIndex
    candidates: List[InterventionCandidate] = Field(..., min_length=1, max_length=10)
    status: CleanText


InterventionRecommendationStorage = RecommendationStorage


class InterventionOutcomeStorage(StorageDocument):
    """Storage model for intervention_outcomes collection (LMS -> C4 feedback)."""
    recommendation_id: str = Field(..., min_length=1)
    decision: Decision
    completed: bool
    observed_change: Optional[CleanText] = Field(default=None, max_length=500)
    notes_present: bool


# ── Core LMS Domain Storage Models ────────────────────────────────────────────

class UserStorage(LegacyIdStorageDocument):
    """Storage model for users collection."""
    email: str = Field(..., min_length=3)
    hashed_password: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    is_active: bool = True
    is_verified: bool = False
    created_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    student_id: Optional[str] = None
    pid: Optional[str] = None
    profile: Optional[Dict[str, Any]] = Field(default=None, description="Embedded profile (Feature 2); free-form object or null")


class IdentityVaultStorage(StorageDocument):
    """Storage model for identity_vault collection (Feature 5)."""
    pid: Pid
    student_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    is_imported: Optional[bool] = Field(default=False, description="Flag indicating externally imported identity")
    source: Optional[str] = Field(default=None, description="Provenance tag e.g. oulad, internal")
    ingestion_run_id: Optional[str] = Field(default=None, description="Ingestion run identifier")
    created_at: Optional[UtcDatetime] = None
    updated_at: Optional[UtcDatetime] = None


class ConsentNoticeStorage(LegacyIdStorageDocument):
    """Storage model for consent_notices collection (Feature 6)."""
    version: int = Field(..., ge=1)
    text: str = Field(..., min_length=10)
    effective_from: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


class ConsentRecordStorage(LegacyIdStorageDocument):
    """Storage model for consent_records collection (Feature 6)."""
    pid: Pid
    notice_version: int = Field(..., ge=1)
    decision: str = Field(..., min_length=1)
    timestamp: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_or_client: Optional[str] = None


class AuditLogStorage(LegacyIdStorageDocument):
    """Storage model for audit_logs collection (Feature 7)."""
    timestamp: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: str = Field(..., min_length=1)
    actor_role: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    outcome: str = Field(default="success")
    reason: Optional[str] = None
    ip_address: str = Field(default="unknown")
    user_agent: str = Field(default="unknown")
    request_id: str = Field(default="unknown")
    details: Optional[Dict[str, Any]] = None


class CourseStorage(LegacyIdStorageDocument):
    """Storage model for courses collection."""
    course_id: CourseId
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    lecturer_id: Optional[str] = Field(default=None, description="ID of the lecturer in charge")
    is_published: bool = False
    presentation_length_days: Optional[int] = Field(default=None, ge=1, description="OULAD presentation duration in days")
    source: Optional[str] = Field(default=None, description="Course source provenance tag (e.g. oulad, demo, internal)")
    ingestion_run_id: Optional[str] = Field(default=None, description="Ingestion run identifier")
    modules: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Course modules list")
    created_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CourseWeekStorage(StorageDocument):
    """Storage model for course_weeks collection."""
    course_id: CourseId
    week_index: WeekIndex
    title: str = Field(..., min_length=1)
    start_date: UtcDatetime
    end_date: UtcDatetime


class EnrolmentStorage(StorageDocument):
    """Storage model for enrolments collection."""
    pid: Pid
    course_id: CourseId
    enrolment_start: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="active", min_length=1)
    enrolment_end: Optional[UtcDatetime] = None
    final_result: Optional[str] = Field(default=None, description="Ground truth outcome e.g. Pass, Distinction, Fail, Withdrawn")
    unregistration_week: Optional[int] = Field(default=None, ge=0, description="Week index when unregistration occurred")
    date_registration: Optional[int] = Field(default=None, description="Raw day offset of registration")
    date_unregistration: Optional[int] = Field(default=None, description="Raw day offset of unregistration")


class AssignmentStorage(StorageDocument):
    """Storage model for assignments collection."""
    assignment_id: str = Field(..., min_length=1)
    course_id: CourseId
    week_index: WeekIndex
    title: str = Field(..., min_length=1)
    due_date: UtcDatetime
    max_points: float = Field(..., ge=0.0)
    assessment_type: Optional[str] = Field(default=None, description="Assessment type e.g. TMA, CMA, Exam")
    weight: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Assessment weight percentage")


class SubmissionStorage(StorageDocument):
    """Storage model for submissions collection."""
    submission_id: str = Field(..., min_length=1)
    assignment_id: str = Field(..., min_length=1)
    pid: Pid
    course_id: CourseId
    submitted_at: UtcDatetime
    score: Optional[float] = Field(default=None, ge=0.0)
    feedback: Optional[str] = None
    is_banked: Optional[bool] = Field(default=False, description="Banked submission from previous presentation")
    delay_hours: Optional[float] = Field(default=None, description="Submission delay relative to assessment date in hours")
    date_submitted: Optional[int] = Field(default=None, description="Raw day offset of submission")


class QuizStorage(StorageDocument):
    """Storage model for quizzes collection."""
    quiz_id: str = Field(..., min_length=1)
    course_id: CourseId
    week_index: WeekIndex
    title: str = Field(..., min_length=1)
    max_score: float = Field(..., ge=0.0)


class QuizAttemptStorage(StorageDocument):
    """Storage model for quiz_attempts collection."""
    attempt_id: str = Field(..., min_length=1)
    quiz_id: str = Field(..., min_length=1)
    pid: Pid
    course_id: CourseId
    score: float = Field(..., ge=0.0)
    completed_at: UtcDatetime


class GradeStorage(WeeklyStorageDocument):
    """Storage model for grades collection."""
    grade_item: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0)
    max_score: float = Field(..., gt=0.0)
    weight_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    assessment_id: Optional[str] = Field(default=None, description="OULAD assessment identifier")


class AttendanceStorage(WeeklyStorageDocument):
    """Storage model for attendance collection."""
    sessions_scheduled: int = Field(..., ge=0)
    sessions_attended: int = Field(..., ge=0)
    attendance_pct: float = Field(..., ge=0.0, le=100.0)


class ActivityEventStorage(StorageDocument):
    """Storage model for activity_events collection (telemetry clickstream)."""
    pid: Pid
    course_id: CourseId
    week_index: WeekIndex
    timestamp: UtcDatetime
    event_type: str = Field(..., min_length=1)
    event_payload: Optional[Dict[str, Any]] = None
    timestamp_precision: Optional[str] = Field(default=None, description="Temporal resolution e.g. 'day', 'second'")
    resource_id: Optional[str] = Field(default=None, description="VLE site/resource identifier")
    clicks: Optional[int] = Field(default=None, ge=0, description="Sum of clicks for daily interaction")
    session_minutes: Optional[float] = Field(default=None, ge=0.0, description="Session duration in minutes")


class InterventionStorage(StorageDocument):
    """Storage model for interventions collection (operational action tracking)."""
    intervention_id: str = Field(..., min_length=1)
    recommendation_id: Optional[str] = None
    pid: Pid
    course_id: CourseId
    intervention_type: str = Field(..., min_length=1)
    status: str = Field(default="proposed", min_length=1)
    created_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SchemaMigrationStorage(StorageDocument):
    """Storage model for schema_migrations collection."""
    id: str = Field(..., min_length=1, description="Sequential migration identifier, e.g. '0001_init'")
    checksum: str = Field(..., min_length=1, description="SHA256 checksum of migration source")
    applied_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionRunStorage(StorageDocument):
    """Storage model for ingestion_runs collection."""
    run_id: str = Field(..., min_length=1)
    component: str = Field(..., min_length=1)
    started_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[UtcDatetime] = None
    status: str = Field(default="running")
    records_processed: int = Field(default=0, ge=0)
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed run metrics and collection counts")
    dry_run: Optional[bool] = Field(default=False, description="Whether run was a dry run")


class PipelineStageStorage(BaseModel):
    """Sub-document tracking an individual component stage within a pipeline run."""
    status: str = Field(
        default="waiting",
        description="Stage status: waiting, ready, notified, receiving, complete, timed_out, skipped, failed",
    )
    since: UtcDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when stage transitioned to current status",
    )
    updated_at: UtcDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last status or progress update",
    )
    note: Optional[str] = Field(default=None, description="Diagnostic, error, or completion summary note")
    coverage: Optional[float] = Field(default=None, description="Coverage ratio (received / eligible)")
    eligible: int = Field(default=0, ge=0, description="Total count of eligible students")
    received: int = Field(default=0, ge=0, description="Count of received component records")
    notified_at: Optional[UtcDatetime] = Field(default=None, description="UTC timestamp when webhook was dispatched")
    notify_attempts: int = Field(default=0, ge=0, description="Webhook delivery attempt count")
    notify_error: Optional[str] = Field(default=None, description="Last webhook error message")

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class PipelineRunStorage(StorageDocument):
    """Storage model for pipeline_runs collection."""
    run_id: str = Field(..., min_length=1, description="Unique pipeline run execution identifier")
    course_id: CourseId = Field(..., description="Target course identifier")
    week_index: WeekIndex = Field(..., description="Zero-indexed academic week")
    week_end: UtcDatetime = Field(..., description="UTC end timestamp of the academic week")
    status: str = Field(
        default="pending",
        description="Run status: pending, running, complete, partial, failed",
    )
    trigger: str = Field(
        default="scheduler",
        description="Execution trigger: scheduler, manual",
    )
    triggered_by: str = Field(
        default="system:scheduler",
        description="Actor who initiated run (e.g. system:scheduler or user ID)",
    )
    started_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[UtcDatetime] = None
    stages: Dict[str, PipelineStageStorage] = Field(
        default_factory=dict,
        description="Stage states keyed by stage name: lms_aggregation, c1, c2, c3, c4",
    )


class SchedulerLockStorage(StorageDocument):
    """Storage model for scheduler_locks collection."""
    id: str = Field(
        default="weekly_pipeline",
        alias="_id",
        description="Fixed lock identifier ('weekly_pipeline')",
    )
    owner: str = Field(..., min_length=1, description="Hostname/PID/Instance that holds lock lease")
    acquired_at: UtcDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: UtcDatetime = Field(..., description="UTC timestamp when lock lease expires")