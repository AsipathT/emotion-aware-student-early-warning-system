"""
backend/app/db/indexes.py

Feature 25: Canonical MongoDB Index Specifications.
Defines pymongo IndexModel lists for every collection across the LMS,
Privacy, Audit, and ML analytics subsystems.

Preserves existing indexes established in Features 1, 5, 6, and 7.
"""

from typing import Dict, List
import pymongo
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.db import collections as col

COLLECTION_INDEXES: Dict[str, List[IndexModel]] = {
    # ── Core LMS Collections ──────────────────────────────────────────────────
    col.USERS: [
        IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
        IndexModel([("role", ASCENDING)], name="idx_users_role"),
    ],
    col.COURSES: [
        IndexModel([("course_id", ASCENDING)], unique=True, name="idx_courses_course_id_unique"),
        IndexModel([("lecturer_id", ASCENDING)], name="idx_courses_lecturer_id"),
    ],
    col.COURSE_WEEKS: [
        IndexModel(
            [("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_course_weeks_compound_unique",
        ),
    ],
    col.ENROLMENTS: [
        # Compound unique index allows re-enrolment across distinct term start dates
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("enrolment_start", ASCENDING)],
            unique=True,
            name="idx_enrolments_pid_course_start_unique",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("status", ASCENDING)],
            name="idx_enrolments_course_status",
        ),
        IndexModel([("pid", ASCENDING)], name="idx_enrolments_pid"),
    ],
    col.ASSIGNMENTS: [
        IndexModel([("assignment_id", ASCENDING)], unique=True, name="idx_assignments_id_unique"),
        IndexModel([("course_id", ASCENDING), ("week_index", ASCENDING)], name="idx_assignments_course_week"),
    ],
    col.SUBMISSIONS: [
        IndexModel([("submission_id", ASCENDING)], unique=True, name="idx_submissions_id_unique"),
        IndexModel([("pid", ASCENDING), ("assignment_id", ASCENDING)], name="idx_submissions_pid_assignment"),
        IndexModel([("course_id", ASCENDING), ("assignment_id", ASCENDING)], name="idx_submissions_course_assignment"),
    ],
    col.QUIZZES: [
        IndexModel([("quiz_id", ASCENDING)], unique=True, name="idx_quizzes_id_unique"),
        IndexModel([("course_id", ASCENDING), ("week_index", ASCENDING)], name="idx_quizzes_course_week"),
    ],
    col.QUIZ_ATTEMPTS: [
        IndexModel([("attempt_id", ASCENDING)], unique=True, name="idx_quiz_attempts_id_unique"),
        IndexModel([("pid", ASCENDING), ("quiz_id", ASCENDING)], name="idx_quiz_attempts_pid_quiz"),
    ],

    # ── Privacy & Ethics Layer (Features 5 & 6) ───────────────────────────────
    col.IDENTITY_VAULT: [
        IndexModel([("pid", ASCENDING)], unique=True, name="idx_vault_pid_unique"),
        IndexModel([("student_id", ASCENDING)], unique=True, name="idx_vault_student_id_unique"),
    ],
    col.CONSENT_NOTICES: [
        IndexModel([("version", ASCENDING)], unique=True, name="idx_consent_notices_version_unique"),
        IndexModel([("is_active", ASCENDING)], name="idx_consent_notices_is_active"),
    ],
    col.CONSENT_RECORDS: [
        IndexModel([("pid", ASCENDING), ("notice_version", ASCENDING)], name="idx_consent_records_pid_version"),
        IndexModel([("timestamp", DESCENDING)], name="idx_consent_records_timestamp_desc"),
    ],

    # ── Audit Log Layer (Feature 7 - Preserved verbatim) ──────────────────────
    col.AUDIT_LOGS: [
        IndexModel([("timestamp", DESCENDING)], name="idx_audit_timestamp_desc"),
        IndexModel([("actor_id", ASCENDING)], name="idx_audit_actor_id"),
        IndexModel([("target_id", ASCENDING)], name="idx_audit_target_id"),
        IndexModel([("action", ASCENDING)], name="idx_audit_action"),
    ],

    # ── Telemetry & Observability ─────────────────────────────────────────────
    col.ACTIVITY_EVENTS: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("timestamp", ASCENDING)],
            name="idx_activity_events_pid_course_time",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("week_index", ASCENDING)],
            name="idx_activity_events_course_week",
        ),
    ],
    col.MESSAGES: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("timestamp", ASCENDING)],
            name="idx_messages_pid_course_time",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("week_index", ASCENDING), ("source_type", ASCENDING)],
            name="idx_messages_course_week_source",
        ),
        IndexModel([("message_id", ASCENDING)], unique=True, name="idx_messages_message_id_unique"),
    ],
    col.GRADES: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_grades_compound_weekly_unique",
        ),
    ],
    col.ATTENDANCE: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_attendance_compound_weekly_unique",
        ),
    ],

    # ── Weekly Analytics Collections (Unique Compound Invariants) ─────────────
    col.BEHAVIOR_WEEKLY: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_behavior_weekly_compound_unique",
        ),
    ],
    col.AFFECTIVE_WEEKLY: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_affective_weekly_compound_unique",
        ),
    ],
    col.ENGAGEMENT_TRAJECTORIES: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_engagement_trajectories_compound_unique",
        ),
    ],
    col.RISK_ASSESSMENTS: [
        IndexModel(
            [("pid", ASCENDING), ("course_id", ASCENDING), ("week_index", ASCENDING)],
            unique=True,
            name="idx_risk_assessments_compound_unique",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("week_index", ASCENDING), ("risk_tier", ASCENDING)],
            name="idx_risk_assessments_course_week_tier",
        ),
    ],

    # ── Recommendations & Interventions (Decision Loop) ──────────────────────
    col.RECOMMENDATIONS: [
        IndexModel([("recommendation_id", ASCENDING)], unique=True, name="idx_recommendations_rec_id_unique"),
        IndexModel([("pid", ASCENDING), ("week_index", ASCENDING)], name="idx_recommendations_pid_week"),
    ],
    col.INTERVENTIONS: [
        IndexModel([("intervention_id", ASCENDING)], unique=True, name="idx_interventions_id_unique"),
        IndexModel([("pid", ASCENDING), ("course_id", ASCENDING)], name="idx_interventions_pid_course"),
        IndexModel([("status", ASCENDING)], name="idx_interventions_status"),
    ],
    col.INTERVENTION_OUTCOMES: [
        IndexModel([("recommendation_id", ASCENDING)], unique=True, name="idx_intervention_outcomes_rec_id_unique"),
        IndexModel([("pid", ASCENDING), ("week_index", ASCENDING)], name="idx_intervention_outcomes_pid_week"),
    ],

    # ── Administrative & Pipeline Metadata ────────────────────────────────────
    col.SCHEMA_MIGRATIONS: [
        IndexModel([("id", ASCENDING)], unique=True, name="idx_schema_migrations_id_unique"),
    ],
    col.INGESTION_RUNS: [
        IndexModel([("run_id", ASCENDING)], unique=True, name="idx_ingestion_runs_id_unique"),
        IndexModel([("component", ASCENDING), ("started_at", DESCENDING)], name="idx_ingestion_runs_component_started"),
    ],
}
