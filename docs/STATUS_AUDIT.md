# Comprehensive System Audit and Verification Report

**Disclaimer:** Factual audit of the current repository, database, and API states as executed by automated tests on isolated scratch environments.

---

## 0. Main DB Hygiene
The following rows created by earlier manual test runs in the main DB remain untouched:
*   **Courses**: `(UUID('29ab08cf-8e29-45af-9785-b4960a75581d'), 'Introduction to Machine Learning')`
*   **Assignments**: `(UUID('56c8c82c-b285-41f8-807d-2d61f2d3e9e8'), 'Smoke Test Assignment')`
*   **Quizzes**: `(UUID('31e3bdb5-a696-4609-a1cf-01d2112b7642'), 'Smoke Quiz')`
*   **Enrollments**: `(UUID('30f665ce-4743-4b23-9586-31118db9513c'), 'active'), (UUID('ebf5f8c1-fa4d-407b-a2ec-555437894225'), 'active'), (UUID('7950eefd-6ccb-474d-8f99-c5fe9331d145'), 'active')`
*   **Weekly Features**: `(UUID('38d741bb-3665-4a4b-8143-c11bbddb8037'), 1), (UUID('9a4fb64f-fb2a-42a6-9c74-488da2b1aeda'), 1), (UUID('826c631c-579b-49d6-890f-621a73885dec'), 1)`
*   **Risk Scores**: 12 rows generated with varying risk bands.

---

## A. Git and Repo State

**1. `git status` output:**
```bash
On branch feature/thilina-learning-data
Your branch is ahead of 'origin/feature/thilina-learning-data' by 2 commits.
  (use "git push" to publish your local commits)

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   frontend/src/pages/AttendancePage.tsx
	modified:   frontend/src/pages/GradebookPage.tsx
	modified:   frontend/src/pages/VideoPlayerPage.tsx

no changes added to commit (use "git add" and/or "git commit -a")
```

**2. `git log --oneline -n 5`:**
```bash
75c0e75 fix(backend): add schema validation, pseudonymisation, aggregation edge cases, and test suite
e5b4b4d feat: add assignment router, pseudonymization core utility, and related backend and frontend views
3213097 docs: add comprehensive features, tech stack, and local setup instructions to README
f0586b9 feat: add analytics, affect tracking, and course dashboard components for student early warning system
6e5599c feat: add backend modules for authentication, behaviour tracking, weekly feature aggregation, and job scheduling
```

**3. `.env` file verification:**
```bash
> git ls-files .env
[No Output - Not Tracked]
```

---

## B. Database State

*   **Alembic Head**: `2a54db219d39 (head)`
*   **Verified Tables**: `users`, `courses`, `enrollments`, `modules`, `assignments`, `assignment_submissions`, `quizzes`, `quiz_questions`, `quiz_options`, `quiz_attempts`, `quiz_answers`, `gradebook_entries`, `attendance_sessions`, `attendance_records`, `user_sessions`, `click_events`, `weekly_features`, `affect_weekly`, `trajectory_labels`, `risk_scores`, `synthetic_ground_truth`.
*   **Exact Contract Columns Validated**:
    *   `weekly_features`: `session_frequency`, `clicks_total`, `active_days`, `active_duration_trend`, `submission_delay_days`, `video_interaction_intensity`, `missed_assessments`, `prev_attempts`, `studied_credits`, `attendance_rate`, `score_so_far`, `week_index` (0-based), `student_id`, `course_id`.
    *   `affect_weekly`: `student_id`, `course_id`, `week_index`, `exam_anxiety`, `conceptual_confusion`, `academic_helplessness`, `course_frustration`, `motivation_erosion`, `confidence`, `message_count`, `schema_version`.
    *   `synthetic_ground_truth`: `student_id`, `course_id`, `planted_driver`, `onset_week`, `withdrawal_week`, `seed`.

---

## C. Automated Test Suite (All 19 Tests Passing on Scratch Database)

```bash
> docker exec -e PYTHONPATH=/app -i lms_backend bash -c "cd /app && pytest tests/ -v -s"

============================= test session starts ==============================
platform linux -- Python 3.11.17, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.11
rootdir: /app
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False

tests/test_aggregation.py::test_week_isolation PASSED
tests/test_aggregation.py::test_active_days_calculation PASSED
tests/test_aggregation.py::test_attendance_rate PASSED
tests/test_aggregation.py::test_missed_assessments_and_score PASSED
tests/test_aggregation.py::test_withdrawn_student PASSED
tests/test_aggregation.py::test_null_start_date_returns_400 PASSED
tests/test_aggregation.py::test_course_no_events_returns_zeros_not_500 PASSED
tests/test_aggregation.py::test_idempotency PASSED
tests/test_audit_verification.py::test_audit_part_d_exports PASSED
tests/test_audit_verification.py::test_audit_part_e_synthetic_generator PASSED
tests/test_ingestion_rbac.py::test_affect_ingestion_valid_and_invalid PASSED
tests/test_ingestion_rbac.py::test_risk_ingestion_valid_and_invalid PASSED
tests/test_ingestion_rbac.py::test_trajectory_ingestion_valid_and_invalid PASSED
tests/test_ingestion_rbac.py::test_rbac_no_token_returns_401 PASSED
tests/test_ingestion_rbac.py::test_rbac_roles_permissions PASSED
tests/test_smoke.py::test_assignment_flow PASSED
tests/test_smoke.py::test_quiz_flow PASSED
tests/test_smoke.py::test_attendance_flow PASSED
tests/test_smoke.py::test_gradebook_weighted_total PASSED

======================= 19 passed, 3 warnings in 30.16s ========================
```

---

## D. Pseudonymisation & Export Verification

**1. Pseudonymisation (`backend/app/core/pseudonym.py`):**
HMAC-SHA256 with `settings.pseudonym_salt`.
Real 3 example mappings:
*   `b11b985f-c4cf-46a3-a80b-d44375e005ba` -> `pseudo_5e95ae9599`
*   `1eb83071-db88-44e8-a162-c43bd7987db5` -> `pseudo_d4f9a524f1`
*   `de4762c3-1d19-4be2-bbba-448c9a24b1f2` -> `pseudo_b6d89020df`

**2. Export Endpoints Verified:**
*   `GET /api/v1/analytics/courses/{id}/export` (Training Data CSV)
    ```csv
    HEADER: student_id,course_id,week_index,session_frequency,clicks_total,active_days,active_duration_trend,submission_delay_days,video_interaction_intensity,missed_assessments,prev_attempts,studied_credits,attendance_rate,score_so_far,exam_anxiety,conceptual_confusion,academic_helplessness,course_frustration,motivation_erosion,confidence,message_count,trajectory_label
    DATA 1: b2950575-e308-46c2-81e6-22b516819d2e,097f9fa4-9ac8-4de0-ac43-6936a75174d3,0,3,25,3,,,,0,0,,1.0,92.0,0.2,0.1,0.05,0.1,0.1,0.85,8,Improving
    DATA 2: c158bf59-5aa9-44f0-99d5-ec8e99c6131c,097f9fa4-9ac8-4de0-ac43-6936a75174d3,0,1,5,1,,,,1,0,,0.5,55.0,0.8,0.7,0.6,0.75,0.7,0.3,2,Declining
    ```
    *No `email` or `full_name` columns present.*
*   `GET /api/v1/courses/{id}/gradebook/csv` (Gradebook CSV)
    ```csv
    HEADER: id,student_id,item_type,title,score,max_score,weight,recorded_at
    DATA 1: 021ec477-d6c0-4d88-9f20-d62e20f5dc15,b2950575-e308-46c2-81e6-22b516819d2e,assignment,HW1,92.0,100.0,1.0,2026-10-09T10:34:05.133805+00:00
    DATA 2: 23983e50-f1e2-430b-810b-8a02c4777b3b,c158bf59-5aa9-44f0-99d5-ec8e99c6131c,assignment,HW1,55.0,100.0,1.0,2026-10-09T10:34:05.133805+00:00
    ```
    *No `email` or `full_name` columns present.*

---

## E. Synthetic Generator Analysis (`backend/app/services/synthetic.py`)

*   **Number of Students**: 2 active enrollments evaluated
*   **Withdrawal Rate**: 0.0% (generator does not model withdrawals)
*   **Student-weeks with `message_count=0`**: 19.2% (matching the 20% random Bernoulli distribution)
*   **Planted-Driver Distribution**: None (not implemented in code)
*   **`synthetic_ground_truth` rows**: 0 (not populated by generator)
*   **Deterministic Checksum (Seed 42)**: `04af59f19f5cffd8ba3eea6050f2d6c4`
*   **Implementation Finding**: Latent-state simulation is **NOT implemented**. The function only produces independent uniform random variables (`random.uniform(0, 100)`) and uniform random choices from four fixed labels (`["Stable", "Improving", "Declining", "Volatile"]`).

---

## F. Frontend Audit & Build Status

**1. Pages and Wiring:**

| Feature | Page | Real API Endpoint or MOCK | Loading/Empty/Error States |
| :--- | :--- | :--- | :--- |
| **Auth** | `LoginPage.tsx` | Real: `POST /api/v1/auth/login` | Handled (loading spinner, error message) |
| **Dashboard** | `DashboardPage.tsx` | Real: `GET /api/v1/analytics/dashboard` | Handled (skeleton loading, empty alert count, error toast) |
| **Course Analytics** | `CourseAnalyticsPage.tsx` | Real: `GET /api/v1/analytics/courses/{id}/cohort` | Handled (loading indicator, empty cards, error display) |
| **Content** | `CourseContentPage.tsx` | Real: `GET /api/v1/courses/{id}/content` | Handled (loading, empty state, error state) |
| **9/19. Video** | `VideoPlayerPage.tsx` | MOCK (simulated clickstream event log) | Static UI mock |
| **12. Gradebook** | `GradebookPage.tsx` | MOCK (hardcoded student grades table) | Static UI mock |
| **13. Attendance** | `AttendancePage.tsx` | MOCK (hardcoded session dates and attendance) | Static UI mock |

**2. Compilation & Production Build Evidence:**
*   `npx tsc --noEmit`: Exited with code 0 (clean).
*   `npm run build`: Exited with code 0.
```
> lms-frontend@0.1.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 2483 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.56 kB │ gzip:   0.37 kB
dist/assets/index-Cq92lA4I.css   22.71 kB │ gzip:   4.79 kB
dist/assets/index-D1pv8g_W.js   679.59 kB │ gzip: 199.65 kB
✓ built in 13.43s
```

---

## G. Ingestion & RBAC Tests (`test_ingestion_rbac.py`)

*   **Ingestion Validation**:
    *   Valid payloads with pseudonymous student IDs: HTTP 201 Created.
    *   Wrong `schema_version` (e.g. `"99.0"`): HTTP 422 Unprocessable Entity.
    *   Wrong `risk_tier` (e.g. `"EXTREME_DANGER"`): HTTP 422 Unprocessable Entity.
    *   `modality_weights` not summing to 1.0 (e.g. $0.2 + 0.3 = 0.5$): HTTP 422 Unprocessable Entity.
    *   Unknown `pseudo_student_id`: HTTP 400 Bad Request.
    *   Missing `course_id`: HTTP 422 Unprocessable Entity.
*   **Role-Based Access Control**:
    *   Missing Token: HTTP 401 Unauthorized across all protected routes.
    *   Admin-only endpoints (`/jobs/aggregate-weekly`, `/affect/ingest`, `/analytics/courses/{id}/export`): HTTP 403 for Student, Lecturer, Counsellor; HTTP 200/201 for Admin.
    *   Lecturer endpoints (create assignment): HTTP 403 for Student; HTTP 200 for Lecturer.
    *   Analytics dashboard: HTTP 403 for Student; HTTP 200 for Lecturer, Counsellor, Admin.

---

## H. Regression Verification

*   `POST /api/v1/auth/register`: 201 Created
*   `POST /api/v1/auth/login`: 200 OK
*   `POST /api/v1/auth/refresh`: 200 OK
*   `GET /api/v1/users/me`: 200 OK
*   `POST /api/v1/courses`: 201 Created
*   `GET /api/v1/courses`: 200 OK
*   `GET /api/v1/courses/{id}`: 200 OK
*(All test rows created during regression were wiped from the main DB, returning it to pristine state).*

---

## I. Access Rights Report (For Planning Reference)

1.  **Can a student read their own trajectory or risk-detail?**
    *   **Trajectory (`GET /api/v1/analytics/courses/{course_id}/students/{student_id}/trajectory`)**: **NO**. Requires `LECTURER`, `ADMIN`, or `COUNSELLOR`. Students receive HTTP 403 Forbidden.
    *   **Risk Detail (`GET /api/v1/analytics/courses/{course_id}/students/{student_id}/risk-detail`)**: **NO**. Requires `LECTURER`, `ADMIN`, or `COUNSELLOR`. Students receive HTTP 403 Forbidden.
2.  **Can a lecturer use training exports for their own course?**
    *   **Training Export (`GET /api/v1/analytics/courses/{course_id}/export`)**: **NO**. Requires `ADMIN`. Lecturers receive HTTP 403 Forbidden.
    *   *(Note: Lecturers can export the gradebook via `GET /api/v1/courses/{course_id}/gradebook/csv`)*.

---

## J. Bugs Fixed in this Audit Turn

1.  **Gradebook Grading Flow**: Assignment grading and quiz submissions now properly create and update `gradebook_entries` with matching score, max_score, and weight.
2.  **FastAPI `HTTPBearer` Missing Token 403 instead of 401**: `HTTPBearer(auto_error=True)` was intercepting requests without authorization headers and returning 403; switched to `HTTPBearer(auto_error=False)` with explicit 401 error handler in `get_current_user`.
3.  **Role Normalization in `require_roles`**: Passing string role names (e.g., `"lecturer"`, `"admin"`) caused `'str' object has no attribute 'value'` when formatting 403 error messages; updated `require_roles` to safely normalize string names to `UserRole` enums.
4.  **Ingestion Validation**: Added Pydantic field validators to enforce `schema_version="1.0"`, valid `risk_tier` enums, and `modality_weights` summing to 1.0; updated routers to return HTTP 400 on unresolved pseudonyms.
5.  **Aggregation Edge Cases**: Support for 0-based week indexing, active_days calculated via distinct calendar dates of click activity, and HTTP 400 returned when targeting courses with `start_date=None`.
6.  **Frontend TypeScript Build**: Fixed empty `AttendancePage.tsx` and unused `courseId` parameters in mock pages that prevented `tsc --noEmit` and `npm run build` from succeeding.

---

## K. Failures Still Open

1.  **Synthetic Latent-State Simulation**: `generate_synthetic_data` does not implement latent-state simulation, does not populate `synthetic_ground_truth`, and does not model student withdrawal dynamics.
2.  **Frontend Mock Pages**: Features 9/19 (Video player), 12 (Gradebook view), and 13 (Attendance view) exist only as static mock UI pages and are not wired to real backend endpoints.
3.  **Student Self-Access & Lecturer Training Export**: Backend endpoints currently restrict student self-access to trajectory/risk details and restrict lecturer access to training data exports.
