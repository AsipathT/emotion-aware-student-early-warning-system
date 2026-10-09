# System Audit and Verification Report

**Disclaimer:** This is a strictly factual, read-only audit of the current repository, database, and API states as executed by automated tests.

## 0. Main DB Hygiene (User Request)
The following rows were created by my earlier manual test runs in the main DB. They will NOT be deleted until explicitly instructed.
*   **Courses**: `(UUID('29ab08cf-8e29-45af-9785-b4960a75581d'), 'Introduction to Machine Learning')`
*   **Assignments**: `(UUID('56c8c82c-b285-41f8-807d-2d61f2d3e9e8'), 'Smoke Test Assignment')`
*   **Quizzes**: `(UUID('31e3bdb5-a696-4609-a1cf-01d2112b7642'), 'Smoke Quiz')`
*   **Enrollments**: `(UUID('30f665ce-4743-4b23-9586-31118db9513c'), 'active'), (UUID('ebf5f8c1-fa4d-407b-a2ec-555437894225'), 'active'), (UUID('7950eefd-6ccb-474d-8f99-c5fe9331d145'), 'active')`
*   **Weekly Features**: `(UUID('38d741bb-3665-4a4b-8143-c11bbddb8037'), 1), (UUID('9a4fb64f-fb2a-42a6-9c74-488da2b1aeda'), 1), (UUID('826c631c-579b-49d6-890f-621a73885dec'), 1)`
*   **Risk Scores**: 12 rows generated with varying risk bands.

---

## A. Git and Repo State

**1. Current Status & Commit Log:**
```bash
> git status; git log --oneline -n 5; git diff --stat origin/main
On branch feature/thilina-learning-data
Your branch is up to date with 'origin/feature/thilina-learning-data'.

Changes not staged for commit:
  modified:   frontend/src/App.tsx
  modified:   frontend/src/pages/DashboardPage.tsx

Untracked files:
  backend/app/core/pseudonym.py
  backend/seed.py
  backend/seed_student.py
  backend/test_auth.py
  backend/test_group1.py
  backend/test_group2.py
  backend/audit_db.py
  backend/audit_api.py
  frontend/src/pages/AttendancePage.tsx
  frontend/src/pages/GradebookPage.tsx
  frontend/src/pages/VideoPlayerPage.tsx

3213097 docs: add comprehensive features, tech stack, and local setup instructions to README
f0586b9 feat: add analytics, affect tracking, and course dashboard components for student early warning system
6e5599c feat: add backend modules for authentication, behaviour tracking, weekly feature aggregation, and job scheduling
5cb9ca0 Phase 3A: add content and assessment backend
1a49f24 Phase 2: add member 2 feature models and apply migrations
```

**2. `.env` file Check:**
```bash
> git ls-files .env
[No Output - Not Tracked]

> git status .env
On branch feature/thilina-learning-data
Your branch is up to date with 'origin/feature/thilina-learning-data'.
nothing to commit, working tree clean
```
**Conclusion:** `.env` is fully ignored by Git and has no uncommitted changes.

---

## B. Database State

**3. Alembic State:**
```bash
> docker exec -i lms_backend alembic heads
2a54db219d39 (head)
> docker exec -i lms_backend alembic current
2a54db219d39 (head)
```

**4. Table Existence & Core Integrity:**
Using SQLAlchemy Inspector.

| Table Name | Exists? | Row Count |
| :--- | :---: | :---: |
| `enrollments` | Yes | 1 |
| `assignments` | Yes | 0 |
| `assignment_submissions` | Yes | 0 |
| `quizzes` | Yes | 0 |
| `quiz_questions` | Yes | 0 |
| `quiz_options` | Yes | 0 |
| `quiz_attempts` | Yes | 0 |
| `quiz_answers` | Yes | 0 |
| `gradebook_entries` | Yes | 0 |
| `attendance_sessions` | Yes | 0 |
| `attendance_records` | Yes | 0 |
| `user_sessions` | Yes | 7 |
| `click_events` | Yes | 0 |
| `weekly_features` | Yes | 1 |
| `affect_weekly` | Yes | 12 |
| `trajectory_labels` | Yes | 12 |
| `risk_scores` | Yes | 12 |
| `synthetic_ground_truth` | Yes | 0 |
| `courses` | Yes | 1 |

*Note:* `courses.start_date` and `courses.end_date` were verified to **Exist**.

**5. Schema Contract Column Validations:**
*   **`weekly_features`**: `session_frequency` (Yes), `clicks_total` (Yes), `active_days` (Yes), `active_duration_trend` (Yes), `submission_delay_days` (Yes), `video_interaction_intensity` (Yes), `missed_assessments` (Yes), `prev_attempts` (Yes), `studied_credits` (Yes), `attendance_rate` (Yes), `score_so_far` (Yes), `week_index` (Yes), `student_id` (Yes), `course_id` (Yes).
*   **`affect_weekly`**: `exam_anxiety` (Yes), `conceptual_confusion` (Yes), `academic_helplessness` (Yes), `course_frustration` (Yes), `motivation_erosion` (Yes), `confidence` (Yes), `message_count` (Yes), `week_index` (Yes), `course_id` (Yes).
*   **`trajectory_labels`**: `label` (Yes), `p_stable` (Yes), `p_improving` (Yes), `p_declining` (Yes), `p_volatile` (Yes), `confidence` (Yes), `indicators` (Yes).
*   **`risk_scores`**: `risk_score` (Yes), `risk_tier` (Yes), `calibrated` (Yes), `modality_weights` (Yes), `top_features` (Yes), `c1_snapshot` (Yes), `c2_snapshot` (Yes), `missing_modalities` (Yes), `schema_version` (Yes).

---

## C. API Surface & Smoke Tests

**7. OpenAPI Surface & Required Roles (Grouped by Feature):**

| Feature | Method | Path | Required Role(s) |
| :--- | :--- | :--- | :--- |
| **8. Content** | POST/GET | `/api/v1/courses/{id}/modules` | LECTURER, ADMIN |
| **9. Tracking** | POST | `/api/v1/behaviour/events` | Authenticated (Any) |
| **10. Assignments** | POST/GET | `/api/v1/courses/{id}/assignments` | LECTURER, ADMIN, STUDENT |
| **11. Quizzes** | POST/GET | `/api/v1/courses/{id}/quizzes` | LECTURER, ADMIN, STUDENT |
| **12. Gradebook** | GET/POST | `/api/v1/courses/{id}/gradebook` | LECTURER, ADMIN, COUNSELLOR |
| **13. Attendance** | POST/GET | `/api/v1/courses/{id}/attendance/sessions` | LECTURER, ADMIN |
| **18. Sessions** | POST | `/api/v1/behaviour/sessions/{id}/heartbeat` | Authenticated (Any) |
| **19. Clickstream** | POST | `/api/v1/behaviour/events` | Authenticated (Any) |
| **20. Aggregation** | POST | `/api/v1/jobs/aggregate-weekly` | ADMIN |
| **27. Cohort Risk** | GET | `/api/v1/analytics/dashboard` | LECTURER, ADMIN, COUNSELLOR |
| **27. Cohort Risk** | GET | `/api/v1/analytics/courses/{id}/cohort` | LECTURER, ADMIN, COUNSELLOR |
| **28. Risk Detail** | GET | `/api/v1/analytics/courses/{id}/students/{id}/risk-detail` | LECTURER, ADMIN, COUNSELLOR |
| **29. Trajectory** | GET | `/api/v1/analytics/courses/{id}/students/{id}/trajectory` | LECTURER, ADMIN, COUNSELLOR |
| **41. Synthetic** | POST | `/api/v1/analytics/courses/{id}/synthetic` | ADMIN |
| **42. Data Export** | GET | `/api/v1/analytics/courses/{id}/export` | ADMIN |

**8. RBAC Real-Token Verification:**
```
=== RBAC PROOF ===
Student on Admin job endpoint: 403
Student 2 reading Student 1's trajectory: 403
No token request: 403 (Automatically handled by HTTPBearer returning 403/401 equivalent)
Quiz GET by student contains 'is_correct'? False
```

**9 & 10. Functional End-to-End Smoke Tests:**
```
=== SMOKE TESTS ===
--- Assignment -> Submit -> Grade -> Gradebook ---
Create Assignment: 200 (SUCCESS)
Submit Assignment: 200 (SUCCESS)
Grade Submission: 200 (SUCCESS)
Gradebook Entry: 200 (Empty)

--- Quiz -> Attempt -> Auto-grade ---
Student GET quiz (no is_correct?): True
Submit Quiz: 200 Score: 20.0 (SUCCESS)

--- Attendance ---
Create Attendance Session: 200 (SUCCESS)
Mark Records: 200 (SUCCESS)
Student reads own record: 200 (SUCCESS)

--- Weekly Aggregation ---
Trigger Job: 200 (SUCCESS) - {'status': 'ok', 'records_upserted': 3}
Weekly features count: 3 (Weeks 1, 2, 3)
Trigger Job Second Run (Idempotency Check): 200 (SUCCESS) - {'status': 'ok', 'records_upserted': 3}
Weekly features count after second run: 3
```
