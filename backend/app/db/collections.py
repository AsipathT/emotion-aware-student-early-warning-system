"""
backend/app/db/collections.py

Feature 25: Canonical MongoDB Collection Constants and Classifications.
Defines string constants for all 24 database collections across the LMS,
Privacy Layer (Feature 5), Ethics (Feature 6), Audit (Feature 7), and
ML Analytics Components (C1, C2, C3, C4).
"""

# ── Core LMS Collections ──────────────────────────────────────────────────────
USERS = "users"
COURSES = "courses"
COURSE_WEEKS = "course_weeks"
ENROLMENTS = "enrolments"
ENROLLMENTS = "enrolments"  # Alias for compatibility with previous naming
ASSIGNMENTS = "assignments"
SUBMISSIONS = "submissions"
QUIZZES = "quizzes"
QUIZ_ATTEMPTS = "quiz_attempts"

# ── Privacy & Ethics Layer (Features 5 & 6) ───────────────────────────────────
IDENTITY_VAULT = "identity_vault"
CONSENT_NOTICES = "consent_notices"
CONSENT_RECORDS = "consent_records"

# ── Audit & Security Layer (Feature 7) ────────────────────────────────────────
AUDIT_LOGS = "audit_logs"

# ── Telemetry & Observability ─────────────────────────────────────────────────
ACTIVITY_EVENTS = "activity_events"
MESSAGES = "messages"
GRADES = "grades"
ATTENDANCE = "attendance"

# ── ML Weekly Vectors & Longitudinal Trajectories (Features 21 & 23) ──────────
BEHAVIOR_WEEKLY = "behavior_weekly"
AFFECTIVE_WEEKLY = "affective_weekly"
ENGAGEMENT_TRAJECTORIES = "engagement_trajectories"
RISK_ASSESSMENTS = "risk_assessments"

# ── Interventions & Decision Loop (Feature 23 & C4) ───────────────────────────
RECOMMENDATIONS = "recommendations"
INTERVENTIONS = "interventions"
INTERVENTION_OUTCOMES = "intervention_outcomes"

# ── System Administration & Migrations ────────────────────────────────────────
SCHEMA_MIGRATIONS = "schema_migrations"
INGESTION_RUNS = "ingestion_runs"

# ── Canonical Collection Groupings ────────────────────────────────────────────

ALL_COLLECTIONS = (
    USERS,
    IDENTITY_VAULT,
    CONSENT_NOTICES,
    CONSENT_RECORDS,
    AUDIT_LOGS,
    COURSES,
    COURSE_WEEKS,
    ENROLMENTS,
    ASSIGNMENTS,
    SUBMISSIONS,
    QUIZZES,
    QUIZ_ATTEMPTS,
    GRADES,
    ATTENDANCE,
    ACTIVITY_EVENTS,
    BEHAVIOR_WEEKLY,
    MESSAGES,
    AFFECTIVE_WEEKLY,
    ENGAGEMENT_TRAJECTORIES,
    RISK_ASSESSMENTS,
    RECOMMENDATIONS,
    INTERVENTIONS,
    INTERVENTION_OUTCOMES,
    SCHEMA_MIGRATIONS,
    INGESTION_RUNS,
)

# Collections that store time-windowed weekly student metrics:
WEEKLY_COLLECTIONS = (
    BEHAVIOR_WEEKLY,
    AFFECTIVE_WEEKLY,
    ENGAGEMENT_TRAJECTORIES,
    RISK_ASSESSMENTS,
    GRADES,
    ATTENDANCE,
)

# Collections created in previous features that may contain existing production data:
EXISTING_COLLECTIONS = (
    USERS,
    IDENTITY_VAULT,
    CONSENT_NOTICES,
    CONSENT_RECORDS,
    AUDIT_LOGS,
)

# Analytics collections that must strictly never store real student identity fields:
ANALYTICS_COLLECTIONS = (
    ACTIVITY_EVENTS,
    MESSAGES,
    ATTENDANCE,
    GRADES,
    BEHAVIOR_WEEKLY,
    AFFECTIVE_WEEKLY,
    ENGAGEMENT_TRAJECTORIES,
    RISK_ASSESSMENTS,
    RECOMMENDATIONS,
    INTERVENTIONS,
    INTERVENTION_OUTCOMES,
)

# Strictly append-only collections:
APPEND_ONLY_COLLECTIONS = (
    AUDIT_LOGS,
    CONSENT_RECORDS,
    INTERVENTION_OUTCOMES,
    SCHEMA_MIGRATIONS,
    INGESTION_RUNS,
)
