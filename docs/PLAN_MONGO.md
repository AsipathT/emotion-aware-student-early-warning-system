# Plan for Remaining MongoDB Migration

## 1. Collections & Indexes
The following collections need to be created and indexed idiomatically in MongoDB:

### Quizzes
- **Collections:** `quizzes`, `quiz_questions` (can embed `options`), `quiz_attempts`, `quiz_answers`.
- **Indexes:** 
  - `quizzes`: `course_id`
  - `quiz_attempts`: `quiz_id`, `student_id`

### Gradebook
- **Collection:** `gradebook_entries`
- **Indexes:** `course_id`, `student_id`, `item_type`, `item_id`

### Attendance
- **Collections:** `attendance_sessions`, `attendance_records`
- **Indexes:** 
  - `attendance_records`: **Unique index** on `(session_id, student_id)` to prevent duplicate marking.

### Behaviour (Sessions / Clickstream)
- **Collections:** `user_sessions`, `activity_events` (replacing `click_events`)
- **Indexes:** 
  - `user_sessions`: `user_id`
  - `activity_events`: `session_id`, `course_id`

### Analytics (Aggregation, Ingestion, Read)
- **Collections:** `behavioral_weekly` (replaces `weekly_features`), `affective_weekly`, `engagement_trajectories` (replaces `trajectory_labels`), `risk_assessments` (replaces `risk_scores`), `synthetic_ground_truth`.
- **Indexes:**
  - **Unique index** on `(student_id, course_id, week_index)` across `behavioral_weekly`, `affective_weekly`, `engagement_trajectories`, and `risk_assessments`.

## 2. Endpoints & Roles
- **Quizzes:** `POST /api/v1/courses/{course_id}/quizzes` (Lecturer/Admin), `POST /api/v1/courses/.../submit` (Student).
- **Gradebook:** `GET /api/v1/courses/{course_id}/gradebook` (Student sees own, Lecturer sees all).
- **Attendance:** `POST /api/v1/courses/{course_id}/attendance/sessions` (Lecturer/Admin), `POST /.../mark` (Lecturer).
- **Behaviour:** `POST /api/v1/analytics/click-events` (Student, authenticated).
- **Analytics/Exports:** `GET /api/v1/analytics/course/{course_id}/risk-scores` (Lecturer/Admin/Counsellor). Exports allow Admin and Counsellors.
- **Synthetic Generator:** Command-line scripts or `POST /api/v1/jobs/synthetic/generate` (Admin only).

## 3. Frontend Wiring
- Ensure API client calls map `_id` to `id` if they haven't been fully mapped on the backend.
- Refactor data fetching (React Query hooks) to match MongoDB-backed endpoints.
- Validate Mock UIs and connect them to real data.

## Questions for Platform Owner
1. Should `quiz_questions` be embedded directly into the `quizzes` document, or kept as a separate collection considering the potential size limit?
2. You have defined `activity_events` and `behavioral_weekly` collections. Should I strictly map my models (`click_events`, `weekly_features`) to these exact names and schema shapes?
3. Should the synthetic generator insert directly into MongoDB collections via Motor, or go through the FastAPI endpoints?
4. How should the frontend handle polling/live-updates for risk scores—are WebSockets necessary or is standard REST sufficient for now?
5. Is there a specific aggregation pipeline pattern you want used for generating the weekly features from the raw activity events, or should I write custom pipelines?
