# Central MongoDB Architecture & Collection Design

**Feature:** Feature 25  
**Engine:** MongoDB Atlas 8.0+ / Motor 3.6+ (Async Driver) with PyMongo 4.x  
**Storage Contract:** Strict `$jsonSchema` Validation with Pydantic v2 Storage Models  

---

## 1. Architectural Invariants & Data Governance

1. **UTC Timezone Awareness**:
   - The Motor client is initialized with `tz_aware=True`.
   - Every stored timestamp is an ISO 8601 UTC date object (`bsonType: "date"`). Naive datetimes without explicit timezone offsets are rejected at the application and schema layers.

2. **Absolute PII Isolation in Analytics**:
   - Identifying student information (`name`, `email`, `student_id`, `registration_id`) is strictly restricted to the `identity_vault` (Feature 5) and core `users` (Feature 1) collections.
   - All analytics, telemetry, weekly aggregates, and ML model collections mandate Pseudonym IDs (`Pid`, matching `^STU_[0-9a-fA-F]{8}$`).
   - Automated referential integrity verification (`scripts/verify_integrity.py`) asserts zero PII field penetration across analytics collections.

3. **Database Versioning vs. Contract Versioning**:
   - **Storage Versioning**: All stored documents contain an integer `schema_version: int = 1` representing database storage evolution.
   - **Contract Versioning**: Inter-subsystem HTTP payloads (Feature 24) communicate via semantic `"major.minor"` strings (`CONTRACT_VERSION = "1.0"`). Storage documents track `source_version: str` to record which contract version generated the record.

4. **Append-Only Collections**:
   - `audit_logs` (Feature 7): Immutable audit events.
   - `consent_records` (Feature 6): Student consent decision history.
   - `intervention_outcomes` (Feature 25 / C4): Historical intervention effectiveness telemetry.
   - `schema_migrations`: Sequential migration ledger.
   - `ingestion_runs`: Data ingestion execution logs.
   No update or delete operations are permitted against these collections.

---

## 2. Collection Directory & Ownership Map

| Collection | Subsystem / Owner | Purpose & Role | Key Fields |
| :--- | :--- | :--- | :--- |
| `users` | Feature 1 (Core Auth) | User authentication & system credentials | `_id`, `email`, `hashed_password`, `role`, `is_active` |
| `identity_vault` | Feature 5 (Privacy Layer) | Pseudonym-to-identity lookup vault | `_id` (`pid`), `pid`, `student_id`, `name`, `email` |
| `consent_notices` | Feature 6 (Ethics & Consent) | Published ethics notices | `_id`, `version`, `text`, `effective_from`, `is_active` |
| `consent_records` | Feature 6 (Ethics & Consent) | Student consent choices (append-only) | `_id`, `pid`, `notice_version`, `decision`, `timestamp` |
| `audit_logs` | Feature 7 (Audit Log) | Append-only system audit trail | `_id`, `timestamp`, `actor_id`, `action`, `target_id` |
| `courses` | Feature 3 (Curriculum) | Course catalog definitions | `_id`, `course_id`, `title`, `lecturer_id`, `is_published` |
| `course_weeks` | Feature 3 (Curriculum) | Academic term weekly timetable | `_id`, `course_id`, `week_index`, `start_date`, `end_date` |
| `enrolments` | Feature 4 (Enrollments) | Student course registrations | `_id`, `pid`, `course_id`, `enrolment_start`, `status` |
| `assignments` | Feature 3 (Assessment) | Course coursework & deadlines | `_id`, `assignment_id`, `course_id`, `week_index`, `due_date` |
| `submissions` | Feature 3 (Assessment) | Student assignment submissions | `_id`, `submission_id`, `assignment_id`, `pid`, `submitted_at` |
| `quizzes` | Feature 3 (Assessment) | Weekly comprehension quizzes | `_id`, `quiz_id`, `course_id`, `week_index`, `max_score` |
| `quiz_attempts` | Feature 3 (Assessment) | Student quiz attempt records | `_id`, `attempt_id`, `quiz_id`, `pid`, `score`, `completed_at` |
| `grades` | Feature 3 (Grades) | Normalized weekly grade items | `_id`, `pid`, `course_id`, `week_index`, `grade_item`, `score` |
| `attendance` | Feature 3 (Attendance) | Weekly attendance rates | `_id`, `pid`, `course_id`, `week_index`, `attendance_pct` |
| `activity_events` | Feature 21 / 22 (Telemetry) | Granular clickstream event stream | `_id`, `pid`, `course_id`, `week_index`, `timestamp`, `event_type` |
| `messages` | Feature 21 (C1 Ingestion) | Scrubbed LMS forum/journal messages | `_id`, `message_id`, `pid`, `course_id`, `clean_text`, `source_type` |
| `behavior_weekly` | Feature 21 / C2 Telemetry | Weekly clickstream and video aggregates | `_id`, `pid`, `course_id`, `week_index`, `login_count`, `clicks` |
| `affective_weekly` | Feature 23 / C1 Output | Aggregated distress class distributions | `_id`, `pid`, `course_id`, `week_index`, `emotion_scores`, `confidence` |
| `engagement_trajectories` | Feature 23 / C2 Output | Longitudinal engagement trend vectors | `_id`, `pid`, `course_id`, `week_index`, `trajectory_label`, `confidence` |
| `risk_assessments` | Feature 23 / C3 Output | Multimodal student dropout risk scores | `_id`, `pid`, `course_id`, `week_index`, `risk_score`, `risk_tier`, `modality_contributions` |
| `recommendations` | Feature 23 / C4 Output | Ranked adaptive intervention actions | `_id`, `recommendation_id`, `pid`, `week_index`, `candidates`, `status` |
| `interventions` | Feature 23 / Staff Operations | Live intervention tracking | `_id`, `intervention_id`, `pid`, `course_id`, `intervention_type`, `status` |
| `intervention_outcomes` | Feature 23 / C4 Feedback | Action disposition & efficacy outcomes | `_id`, `recommendation_id`, `decision`, `completed`, `notes_present` |
| `schema_migrations` | Feature 25 (Migrations) | Database migration tracking ledger | `_id`, `id`, `checksum`, `applied_at` |
| `ingestion_runs` | Feature 25 (Pipelines) | Telemetry ingestion batch run history | `_id`, `run_id`, `component`, `started_at`, `status` |

---

## 3. Database Indexes Specification

### Compound Weekly Uniqueness
All time-series weekly aggregations enforce compound unique indexes on `(pid, course_id, week_index)`:
- `behavior_weekly`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)
- `affective_weekly`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)
- `engagement_trajectories`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)
- `risk_assessments`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)
- `grades`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)
- `attendance`: `{"pid": 1, "course_id": 1, "week_index": 1}` (unique)

### Re-enrolment & Curriculum Invariants
- `enrolments`: `{"pid": 1, "course_id": 1, "enrolment_start": 1}` (unique). This composite key permits legitimate re-enrolments across subsequent academic terms. Additional secondary index on `{"course_id": 1, "status": 1}` accelerates cohort filtering.
- `course_weeks`: `{"course_id": 1, "week_index": 1}` (unique).

### High-Volume Telemetry & Message Indexes
- `activity_events`:
  - `{"pid": 1, "course_id": 1, "timestamp": 1}`
  - `{"course_id": 1, "week_index": 1}`
- `messages`:
  - `{"pid": 1, "course_id": 1, "timestamp": 1}`
  - `{"course_id": 1, "week_index": 1, "source_type": 1}`
  - `{"message_id": 1}` (unique)

### Decision Loop & Operational Lookups
- `risk_assessments`: Secondary index on `{"course_id": 1, "week_index": 1, "risk_tier": 1}` for high-priority risk filtering.
- `recommendations` & `intervention_outcomes`: `{"pid": 1, "week_index": 1}` and `{"recommendation_id": 1}` (unique).
- `identity_vault`: `{"pid": 1}` (unique) and `{"student_id": 1}` (unique).
- `users`: `{"email": 1}` (unique).
- `audit_logs`: Preserved from Feature 7: `{"timestamp": -1}`, `{"actor_id": 1}`, `{"target_id": 1}`, `{"action": 1}`.

---

## 4. Architectural Decision: Standard Collection for `activity_events`

`activity_events` is provisioned as a standard collection with compound indexes rather than a MongoDB Time Series collection for the following architectural reasons:

1. **Design Simplicity & Flexibility**:
   Standard collections provide full support for arbitrary multi-field updates, ad-hoc document corrections, and seamless sharding/indexing without the constraints imposed on MongoDB time series metaFields and granularity declarations.
2. **Revisit Trigger**:
   If clickstream event volume at OULAD scale (> 10 million events) causes cohort aggregation query latency to exceed **500 ms** (p95), `activity_events` will be migrated to a dedicated MongoDB Time Series collection (`timeField: "timestamp"`, `metaField: "pid"`, `granularity: "seconds"`).

---

## 5. MongoDB Atlas Security & User Role Separation

For production deployments on MongoDB Atlas, configure three distinct database user accounts:

1. **Application Core User (`lms_app_user`)**:
   - Role: `readWrite` on `lms_db`.
   - Used by the primary FastAPI application services.
2. **Audit Logging Service User (`lms_audit_user`)**:
   - Custom Role: `insert` and `find` ONLY on `lms_db.audit_logs`.
   - Strictly denied `update` and `remove` privileges to enforce immutable audit compliance.
3. **ML Component Integration User (`lms_component_user`)**:
   - Role: `read` on `lms_db.courses`, `lms_db.course_weeks`, `lms_db.messages`, `lms_db.behavior_weekly`.
   - Dedicated `readWrite` on respective component output collections (`affective_weekly`, `engagement_trajectories`, `risk_assessments`, `recommendations`).
   - Strictly denied access to `users` and `identity_vault`.
