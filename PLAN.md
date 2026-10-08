# PLAN.md — Member 2 Implementation Plan

> Branch: `feature/thilina-learning-data`
> Features: 8, 9, 10, 11, 12, 13, 18, 19, 20, 27, 28, 29, 41, 42

---

## 1. Database Tables

All tables use UUID PKs, `created_at`/`updated_at` TIMESTAMPTZ columns, and follow existing naming conventions.

### 1.1 `enrollments` (Feature prerequisite — owned by Member 1, created minimally here)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | default uuid4 |
| user_id | UUID FK→users.id | ON DELETE CASCADE, NOT NULL |
| course_id | UUID FK→courses.id | ON DELETE CASCADE, NOT NULL |
| status | Enum('active','withdrawn','completed') | NOT NULL, default 'active' |
| enrolled_at | TIMESTAMPTZ | server_default=now() |
| withdrawn_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | server_default=now() |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate |
| **UNIQUE** | (user_id, course_id) | |
| **INDEX** | user_id, course_id, status | |

### 1.2 Additive columns on `courses`
| Column | Type | Notes |
|---|---|---|
| start_date | Date | nullable, used as week-0 anchor for weekly aggregation |
| end_date | Date | nullable |

### 1.3 `assignments` (Feature 10)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| title | String(255) | NOT NULL |
| description | Text | nullable |
| due_at | TIMESTAMPTZ | nullable |
| max_score | Float | NOT NULL, default 100 |
| weight | Float | NOT NULL, default 1.0 |
| is_published | Boolean | default False |
| created_at / updated_at | TIMESTAMPTZ | standard |

### 1.4 `assignment_submissions` (Feature 10)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| assignment_id | UUID FK→assignments.id | ON DELETE CASCADE |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| submitted_at | TIMESTAMPTZ | server_default=now() |
| content_text | Text | nullable |
| file_url | String(2048) | nullable |
| score | Float | nullable |
| feedback | Text | nullable |
| graded_by | UUID FK→users.id | nullable, ON DELETE SET NULL |
| graded_at | TIMESTAMPTZ | nullable |
| is_late | Boolean | default False |
| delay_days | Integer | default 0 |
| created_at / updated_at | TIMESTAMPTZ | standard |
| **UNIQUE** | (assignment_id, student_id) | one submission per student |

### 1.5 `quizzes` (Feature 11)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| title | String(255) | NOT NULL |
| description | Text | nullable |
| open_at | TIMESTAMPTZ | nullable |
| close_at | TIMESTAMPTZ | nullable |
| time_limit_minutes | Integer | nullable |
| max_attempts | Integer | default 1 |
| max_score | Float | default 100 |
| weight | Float | default 1.0 |
| is_published | Boolean | default False |
| created_at / updated_at | TIMESTAMPTZ | standard |

### 1.6 `quiz_questions` (Feature 11)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| quiz_id | UUID FK→quizzes.id | ON DELETE CASCADE |
| text | Text | NOT NULL |
| question_type | Enum('mcq','true_false') | NOT NULL |
| points | Float | default 1.0 |
| order | Integer | default 1 |
| created_at / updated_at | TIMESTAMPTZ | standard |

### 1.7 `quiz_options` (Feature 11)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| question_id | UUID FK→quiz_questions.id | ON DELETE CASCADE |
| text | String(1000) | NOT NULL |
| is_correct | Boolean | default False |
| order | Integer | default 1 |

### 1.8 `quiz_attempts` (Feature 11)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| quiz_id | UUID FK→quizzes.id | ON DELETE CASCADE |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| started_at | TIMESTAMPTZ | server_default=now() |
| submitted_at | TIMESTAMPTZ | nullable |
| score | Float | nullable |
| created_at / updated_at | TIMESTAMPTZ | standard |

### 1.9 `quiz_answers` (Feature 11)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| attempt_id | UUID FK→quiz_attempts.id | ON DELETE CASCADE |
| question_id | UUID FK→quiz_questions.id | ON DELETE CASCADE |
| selected_option_id | UUID FK→quiz_options.id | nullable, ON DELETE SET NULL |
| created_at | TIMESTAMPTZ | standard |

### 1.10 `gradebook_entries` (Feature 12)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| item_type | Enum('assignment','quiz','exam','manual') | NOT NULL |
| item_id | UUID | nullable (links to assignment/quiz/etc) |
| title | String(255) | NOT NULL |
| score | Float | NOT NULL |
| max_score | Float | NOT NULL |
| weight | Float | default 1.0 |
| recorded_at | TIMESTAMPTZ | server_default=now() |
| created_at / updated_at | TIMESTAMPTZ | standard |
| **INDEX** | (course_id, student_id) | |

### 1.11 `attendance_sessions` (Feature 13)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| title | String(255) | NOT NULL |
| session_date | Date | NOT NULL |
| created_by | UUID FK→users.id | ON DELETE SET NULL |
| created_at / updated_at | TIMESTAMPTZ | standard |

### 1.12 `attendance_records` (Feature 13)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK→attendance_sessions.id | ON DELETE CASCADE |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| status | Enum('present','late','absent','excused') | NOT NULL |
| marked_at | TIMESTAMPTZ | server_default=now() |
| marked_by | UUID FK→users.id | nullable, ON DELETE SET NULL |
| created_at / updated_at | TIMESTAMPTZ | standard |
| **UNIQUE** | (session_id, student_id) | |

### 1.13 `user_sessions` (Feature 18)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id | ON DELETE CASCADE |
| login_at | TIMESTAMPTZ | server_default=now() |
| last_seen_at | TIMESTAMPTZ | nullable |
| logout_at | TIMESTAMPTZ | nullable |
| ip_address | String(45) | nullable |
| user_agent | String(512) | nullable |
| duration_seconds | Integer | nullable |
| created_at / updated_at | TIMESTAMPTZ | standard |
| **INDEX** | (user_id, login_at) | |

### 1.14 `click_events` (Features 9, 19)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id | ON DELETE CASCADE |
| course_id | UUID FK→courses.id | nullable, ON DELETE SET NULL |
| module_id | UUID FK→modules.id | nullable, ON DELETE SET NULL |
| session_id | UUID FK→user_sessions.id | nullable, ON DELETE SET NULL |
| event_type | String(50) | NOT NULL |
| resource_type | String(50) | nullable |
| resource_id | UUID | nullable |
| payload | JSONB | nullable |
| occurred_at | TIMESTAMPTZ | server_default=now() |
| client_ts | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | server_default=now() |
| **INDEX** | (user_id, occurred_at) | |
| **INDEX** | (course_id, occurred_at) | |

Video events: `event_type` in `[video_play, video_pause, video_seek, video_ended, video_ratechange, video_progress]`, payload: `{position_s, duration_s, playback_rate}`.

### 1.15 `weekly_features` (Feature 20)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| week_index | Integer | NOT NULL (0-based) |
| week_start | Date | NOT NULL |
| total_clicks | Integer | default 0 |
| total_time_seconds | Integer | default 0 |
| content_views | Integer | default 0 |
| video_play_seconds | Integer | default 0 |
| assignment_submissions | Integer | default 0 |
| quiz_attempts_count | Integer | default 0 |
| forum_posts | Integer | default 0 |
| avg_score | Float | nullable |
| score_trend | Float | nullable |
| attendance_rate | Float | nullable |
| sessions_count | Integer | default 0 |
| avg_session_duration | Float | nullable |
| distinct_days_active | Integer | default 0 |
| late_submissions | Integer | default 0 |
| score_so_far | Float | nullable |
| computed_at | TIMESTAMPTZ | server_default=now() |
| created_at / updated_at | TIMESTAMPTZ | standard |
| **UNIQUE** | (student_id, course_id, week_index) | |
| **INDEX** | (student_id, course_id, week_index) | |

### 1.16 `risk_scores` (Feature 27, 28)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| week_index | Integer | NOT NULL |
| risk_score | Float | NOT NULL (0.0–1.0) |
| risk_tier | Enum('low','medium','high','critical') | NOT NULL |
| calibrated | Boolean | default False |
| modality_weights | JSONB | nullable |
| top_features | JSONB | nullable |
| c1_snapshot | JSONB | nullable (Component 1: affective) |
| c2_snapshot | JSONB | nullable (Component 2: behavioural) |
| missing_modalities | JSONB | nullable |
| schema_version | String(20) | NOT NULL, default '1.0' |
| model_version | String(50) | nullable |
| created_at | TIMESTAMPTZ | standard |
| **UNIQUE** | (student_id, course_id, week_index) | |

### 1.17 `trajectory_labels` (Feature 29)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| week_index | Integer | NOT NULL |
| label | Enum('Stable','Improving','Declining','Volatile') | NOT NULL |
| p_stable | Float | nullable |
| p_improving | Float | nullable |
| p_declining | Float | nullable |
| p_volatile | Float | nullable |
| confidence | Float | nullable |
| indicators | JSONB | nullable |
| schema_version | String(20) | NOT NULL, default '1.0' |
| created_at | TIMESTAMPTZ | standard |
| **UNIQUE** | (student_id, course_id, week_index) | |

### 1.18 `synthetic_ground_truth` (Feature 41)
| Column | Type | Constraints |
|---|---|---|
| id | UUID PK | |
| student_id | UUID FK→users.id | ON DELETE CASCADE |
| course_id | UUID FK→courses.id | ON DELETE CASCADE |
| planted_driver | String(50) | NOT NULL ('affective', 'behavioural', 'academic') |
| onset_week | Integer | NOT NULL |
| withdrawal_week | Integer | nullable |
| seed | Integer | NOT NULL |
| created_at | TIMESTAMPTZ | standard |

---

## 2. API Endpoints

### 2.1 Content / Course Pages (Feature 8)
| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/courses/{course_id}/content` | any auth | Returns modules with rendered content_payload |
| PATCH | `/api/v1/courses/{course_id}/modules/{module_id}/content` | lecturer, admin | Update module content_payload |

### 2.2 Assignments (Feature 10)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/courses/{cid}/assignments` | lecturer, admin | Create assignment |
| GET | `/api/v1/courses/{cid}/assignments` | any auth | List assignments (students see published only) |
| GET | `/api/v1/courses/{cid}/assignments/{aid}` | any auth | Get single assignment |
| PATCH | `/api/v1/courses/{cid}/assignments/{aid}` | lecturer, admin | Update assignment |
| DELETE | `/api/v1/courses/{cid}/assignments/{aid}` | lecturer, admin | Delete assignment |
| POST | `/api/v1/courses/{cid}/assignments/{aid}/submit` | student | Submit assignment |
| GET | `/api/v1/courses/{cid}/assignments/{aid}/submissions` | lecturer, admin | List all submissions |
| POST | `/api/v1/courses/{cid}/assignments/{aid}/submissions/{sid}/grade` | lecturer, admin | Grade a submission |

### 2.3 Quizzes (Feature 11)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/courses/{cid}/quizzes` | lecturer, admin | Create quiz |
| GET | `/api/v1/courses/{cid}/quizzes` | any auth | List quizzes |
| GET | `/api/v1/courses/{cid}/quizzes/{qid}` | any auth | Get quiz (students: no is_correct) |
| PATCH | `/api/v1/courses/{cid}/quizzes/{qid}` | lecturer, admin | Update quiz |
| POST | `/api/v1/courses/{cid}/quizzes/{qid}/questions` | lecturer, admin | Add question with options |
| POST | `/api/v1/courses/{cid}/quizzes/{qid}/start` | student | Start an attempt |
| POST | `/api/v1/courses/{cid}/quizzes/{qid}/attempts/{attid}/answer` | student | Submit answer |
| POST | `/api/v1/courses/{cid}/quizzes/{qid}/attempts/{attid}/submit` | student | Finalize attempt (auto-grade) |
| GET | `/api/v1/courses/{cid}/quizzes/{qid}/attempts` | lecturer, admin | List all attempts |
| GET | `/api/v1/courses/{cid}/quizzes/{qid}/attempts/mine` | student | Get own attempts |

### 2.4 Gradebook (Feature 12)
| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/courses/{cid}/gradebook` | lecturer, admin, counsellor | Full course grid |
| GET | `/api/v1/courses/{cid}/gradebook/me` | student | Own grades |
| GET | `/api/v1/courses/{cid}/gradebook/csv` | lecturer, admin | CSV download |
| POST | `/api/v1/courses/{cid}/gradebook` | lecturer, admin | Manual entry |

### 2.5 Attendance (Feature 13)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/courses/{cid}/attendance/sessions` | lecturer, admin | Create session |
| GET | `/api/v1/courses/{cid}/attendance/sessions` | any auth | List sessions |
| POST | `/api/v1/courses/{cid}/attendance/sessions/{sid}/records` | lecturer, admin | Bulk mark attendance |
| GET | `/api/v1/courses/{cid}/attendance/sessions/{sid}/records` | lecturer, admin | Get records for session |
| GET | `/api/v1/courses/{cid}/attendance/me` | student | Own attendance |

### 2.6 Session Tracking (Feature 18)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/sessions/heartbeat` | any auth | Heartbeat (update last_seen_at) |
| POST | `/api/v1/sessions/logout` | any auth | Explicit logout (close session) |
| GET | `/api/v1/sessions/me` | any auth | Own session history |

Login hook: Create `user_sessions` row inside the existing login endpoint (additive — after TokenResponse is built).

### 2.7 Clickstream (Features 9, 19)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/events` | any auth | Batch click event ingestion (max 100) |

### 2.8 Weekly Aggregation Job (Feature 20)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/admin/jobs/weekly-aggregation/run` | admin | Manually trigger weekly aggregation |

Plus APScheduler cron job running weekly inside the app lifespan.

### 2.9 Analytics — Ingestion (Feature 23-adjacent, for 27/28/29)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/analytics/risk-scores` | admin | Ingest risk_scores batch |
| POST | `/api/v1/analytics/trajectory-labels` | admin | Ingest trajectory_labels batch |

### 2.10 Analytics — Read (Features 27, 28, 29)
| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/analytics/courses/{cid}/cohort-risk` | lecturer, counsellor, admin | Cohort risk overview |
| GET | `/api/v1/analytics/students/{sid}/risk-detail` | lecturer, counsellor, admin, self | Student risk detail |
| GET | `/api/v1/analytics/students/{sid}/trajectory` | lecturer, counsellor, admin, self | Engagement trajectory |

### 2.11 Synthetic Data (Feature 41)
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/v1/admin/synthetic/generate` | admin | Generate synthetic data |
| DELETE | `/api/v1/admin/synthetic/reset` | admin | Delete all synthetic data |

### 2.12 Data Export (Feature 42)
| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/export/weekly-features` | admin, lecturer | CSV/JSON |
| GET | `/api/v1/export/trajectory-labels` | admin, lecturer | CSV/JSON |
| GET | `/api/v1/export/risk-scores` | admin, lecturer | CSV/JSON |
| GET | `/api/v1/export/gradebook` | admin, lecturer | CSV/JSON |
| GET | `/api/v1/export/attendance` | admin, lecturer | CSV/JSON |
| GET | `/api/v1/export/click-events` | admin | CSV/JSON (date-ranged, streamed) |
| GET | `/api/v1/export/training-table` | admin, lecturer | Joined table with "withdraws within k weeks" label |

All exports pseudonymise identifiers (UUID → hash, no emails/names).

---

## 3. Frontend Pages and Components

### 3.1 New Pages
| Page | Route | Roles | Description |
|---|---|---|---|
| CourseDetailPage | `/courses/:courseId` | all | Course content with module list |
| ModuleContentPage | `/courses/:courseId/modules/:moduleId` | all | Module content viewer (text, video, resources) |
| AssignmentsPage | `/courses/:courseId/assignments` | all | Assignment list |
| AssignmentDetailPage | `/courses/:courseId/assignments/:assignmentId` | all | View/submit/grade assignment |
| QuizzesPage | `/courses/:courseId/quizzes` | all | Quiz list |
| QuizTakePage | `/courses/:courseId/quizzes/:quizId/take` | student | Take a quiz |
| GradebookPage | `/courses/:courseId/gradebook` | lecturer, admin, counsellor | Full gradebook grid |
| StudentGradesPage | `/courses/:courseId/grades` | student | Own grades |
| AttendancePage | `/courses/:courseId/attendance` | lecturer, admin | Attendance management |
| CohortRiskPage | `/courses/:courseId/risk` | lecturer, counsellor, admin | Cohort risk overview |
| StudentRiskDetailPage | `/students/:studentId/risk` | lecturer, counsellor, admin, self | Student risk detail |
| EngagementTrajectoryPage | `/students/:studentId/trajectory` | lecturer, counsellor, admin, self | Trajectory timeline |
| AdminSyntheticPage | `/admin/synthetic` | admin | Generate/reset synthetic data |
| AdminExportPage | `/admin/export` | admin | Data export downloads |

### 3.2 New Components
- `VideoPlayer` — HTML5 video player that fires clickstream events (play, pause, seek, ended, ratechange, progress)
- `ContentRenderer` — Renders `content_payload` blocks (markdown, video, resource links)
- `GradebookGrid` — Table with weighted scores
- `AttendanceGrid` — Bulk attendance marking
- `RiskBadge` — Color-coded risk tier badge
- `TrajectoryChart` — Recharts line chart for trajectory labels over weeks
- `RiskHeatmap` — Cohort risk visualization
- `HeartbeatProvider` — Wrapper component that sends periodic heartbeats (every 60s)
- `ClickstreamProvider` — Context provider that buffers and sends click events
- `CourseNav` — Sub-navigation within a course (Content, Assignments, Quizzes, Gradebook, Attendance, Risk)

### 3.3 Changes to Existing Files
- **App.tsx**: Add new routes (additive only).
- **Navbar.tsx**: Add role-based nav links (Courses, Analytics, Admin dropdown).
- **api/client.ts**: No changes.
- **hooks/useAuth.ts**: No changes.

---

## 4. Ordered Task List

### Phase 2: Database
1. Add `start_date` and `end_date` to Course model
2. Create enrollment model (`models/enrollment.py`)
3. Create assessment models (`models/assessment.py`: Assignment, AssignmentSubmission, Quiz, QuizQuestion, QuizOption, QuizAttempt, QuizAnswer)
4. Create gradebook model (`models/gradebook.py`)
5. Create attendance model (`models/attendance.py`)
6. Create behaviour models (`models/behaviour.py`: UserSession, ClickEvent)
7. Create analytics models (`models/analytics.py`: WeeklyFeature, RiskScore, TrajectoryLabel, SyntheticGroundTruth)
8. Register all models in `models/__init__.py` and `alembic/env.py`
9. Generate single Alembic migration, review, apply
10. Verify single head and existing data intact

### Phase 3A: Content + Assessment Backend
11. Schemas: assignment, quiz, gradebook, attendance
12. Router: content pages (render module content_payload)
13. Router: assignments CRUD + submit + grade
14. Router: quizzes CRUD + start + answer + submit (auto-grade)
15. Router: gradebook (grid, own view, CSV, manual entry)
16. Router: attendance (sessions, bulk mark, own view)
17. Register routers in main.py
18. Test via Swagger

### Phase 3B: Behaviour Data Backend
19. Schemas: user_sessions, click_events
20. Hook login flow to create user_sessions row (additive to auth.py)
21. Router: sessions (heartbeat, logout, history)
22. Router: events (batch ingestion)
23. Service: weekly aggregation computation
24. Job: APScheduler cron + admin manual trigger endpoint
25. Register routers in main.py
26. Test aggregation

### Phase 3C+3D: Analytics + Synthetic + Export
27. Schemas: risk_scores, trajectory_labels, export, synthetic
28. Router: analytics ingestion + read endpoints
29. Service: synthetic data generator
30. Router: synthetic generate/reset
31. Router: data export (CSV/JSON, pseudonymised, streamed)
32. Register routers in main.py
33. Generate synthetic data, run weekly job, verify counts

### Phase 4: Frontend
34. Install any new npm packages (if needed — likely `react-markdown` for content rendering)
35. Create API modules for each feature area
36. Create shared components (VideoPlayer, ContentRenderer, RiskBadge, etc.)
37. Create HeartbeatProvider + ClickstreamProvider
38. Create course detail + module content pages
39. Create assignment pages (list, detail, submit, grade)
40. Create quiz pages (list, take)
41. Create gradebook + attendance pages
42. Create analytics pages (cohort risk, student risk, trajectory)
43. Create admin pages (synthetic, export)
44. Update App.tsx with routes
45. Update Navbar.tsx with nav links
46. Test all pages

### Phase 5: Verification
47. Verify existing auth/users/courses still work
48. Verify all new endpoints via Swagger
49. Verify frontend pages render correctly
50. Verify synthetic data + weekly job + exports

---

## 5. Assumptions

1. **Enrollment table**: I will create a minimal `enrollments` table since it does not exist and is needed by assignments, quizzes, attendance, and the weekly aggregation job. Member 1 can extend it later.
2. **Course `start_date`**: I will add `start_date` (Date, nullable) to the Course model. Week-0 is defined as the ISO week containing `start_date`. If `start_date` is NULL, the weekly aggregation job skips that course.
3. **Content payload convention**: `content_payload` in modules is a JSON object with a `blocks` array. Each block has `{type: "text"|"video"|"resource", ...}`. Text blocks have `body` (markdown). Video blocks have `url`, `title`. Resource blocks have `url`, `title`, `mime_type`. I will document this and build the frontend renderer accordingly.
4. **Pseudonymisation**: Since Member 1's pseudonymisation layer (Feature 5) does not exist yet, exports will use a SHA-256 hash of the user UUID as the pseudonymous identifier. No emails or names will be included.
5. **No file upload**: Assignment submissions use `content_text` (plain text/markdown) and optionally `file_url` (externally hosted). I will not implement actual file storage.
6. **Forum posts**: The `forum_posts` column in `weekly_features` will always be 0 until a forum feature is implemented. The column is there for schema completeness.
7. **APScheduler guard**: To prevent double-scheduling when uvicorn reloads, I will use a file-based lock or check if the scheduler is already running.
8. **Synthetic email domain**: Synthetic students use `@synthetic.lms.edu` email domain for easy identification and bulk deletion.

---

## 6. Questions for the Developer (max 5)

1. **Enrollment model ownership**: I need to create an `enrollments` table for my features. Is it OK if I create a minimal version now, and you (Member 1) extend it later? Or do you want to create it first?

2. **Course `start_date`**: I plan to add `start_date` and `end_date` columns to the `courses` table (nullable Date). The weekly aggregation job uses `start_date` as the week-0 anchor. Is this acceptable, or do you have a different plan for course scheduling?

3. **Content payload format**: The `modules.content_payload` column is currently JSON with no documented schema. I plan to render it as an array of blocks: `[{type: "text", body: "..."}, {type: "video", url: "...", title: "..."}, {type: "resource", url: "...", title: "..."}]`. Does this align with your intent?

4. **Video hosting**: Should the video player use external URLs (YouTube/Vimeo embed or direct MP4 links), or should I plan for local video storage? I'm assuming external URLs for now.

5. **Synthetic data scope**: Should synthetic data include counsellor accounts and intervention records, or just students/courses/assessments/behaviour? I'm planning the latter for now since interventions are outside my feature scope.

---

## 7. Dependencies on Other Members

| Feature | Depends on | Status | My approach |
|---|---|---|---|
| Enrollment (4) | Member 1 | Not implemented | Create minimal table, comment "owned by Member 1" |
| Pseudonymization (5) | Member 1 | Not implemented | Use SHA-256(UUID) for exports |
| Audit log (7) | Member 1 | Not implemented | Skip audit logging for now |
| Central ingestion (23) | Member 1 | Not implemented | Create own ingestion endpoints for risk/trajectory |
| OULAD import (26) | Member 1 | Not implemented | Not needed; synthetic generator replaces it for testing |
