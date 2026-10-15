# Feature 40: Admin & Governance Panel Documentation

This document specifies the architecture, route contracts, role-based authorization matrix, audit trail, security safeguards, and manual verification procedures for the LMS Admin Panel.

---

## 1. Overview & Architectural Scope

The Admin Panel is the operational and governance console for Member 1 (Platform Foundation and Integration Layer) of research project **J26-IT-349: "AI-Driven Early Warning System for Student Dropout in Higher Education"** (SLIIT).

It governs and monitors:
- **Features 1–4**: User accounts, course catalogs, enrolments, role-based access.
- **Features 5–6**: Pseudonymization (PID `STU_xxxxxxxx`), consent notice lifecycle, break-glass identity reveals, PII scrubbing.
- **Feature 7**: Immutable audit trail and compliance reporting.
- **Features 21 & 23**: Component egress (Feature 21 export) and ingress (Feature 23 ingestion).
- **Feature 22**: Weekly orchestrator and stage progression pipeline (C1 -> C2 -> C3 -> C4).
- **Features 24–26**: Contract versioning (`1.0.0`), MongoDB schema validation, OULAD dataset imports.

---

## 2. Admin Console Sections

| Section | Route | Description | Primary Role Access |
| :--- | :--- | :--- | :--- |
| **Overview** | `/admin` | Real-time platform KPI cards, user distribution charts, consent coverage rate, ingestion health, and quick actions. | Admin, Auditor |
| **Users** | `/admin/users` | User directory with search, role/status filtering, pagination, account provisioning drawer, role change, status toggle, and profile edit. | Admin only |
| **Courses** | `/admin/courses` | Course catalog, publish/unpublish toggles, lecturer reassignment modal. | Admin, Auditor (Read-only) |
| **Enrolments** | `/admin/enrolments` | Student enrolments by course, single enrolment/soft un-enrolment, bulk CSV enrolment with row-level validation. | Admin, Auditor (Read-only) |
| **Consent** | `/admin/consent` | Overall & per-course consent breakdown, notice version publishing form with mandatory version increment. | Admin, Auditor (Read-only) |
| **Audit Logs** | `/admin/audit` | Embedded Feature 7 compliance viewer with actor/action/target filters, date ranges, and CSV export. | Admin, Auditor |
| **Pipeline** | `/admin/pipeline` | Weekly batch orchestrator monitor, per-stage visualizer (C1–C4), manual Trigger and Advance modals. | Admin, Auditor (Read-only) |
| **Ingestion** | `/admin/ingestion` | Ingestion health grid for ML components (C1–C4), last success/error timestamps, acceptance counters. | Admin, Auditor |
| **Privacy & Ethics** | `/admin/privacy` | Break-glass identity reveal with mandatory >=10 char justification, reveal audit log, ephemeral PII scrubber tester. | Admin (Reveal), Auditor (Logs & Scrub) |
| **Exports** | `/admin/exports` | Export datasets (`c1_messages`, `c2_behavior`, `c3_academic`, `c3_affective`, `c3_trajectories`, `c4_risk`, `c4_recommendations`) with formula sanitization. | Admin, Auditor |
| **System Diagnostics** | `/admin/system` | MongoDB latency ping (ms), applied database migrations (`0001`–`0007`), OULAD dataset import metrics, scheduler locks. | Admin, Auditor |

---

## 3. API Endpoints Reference

### User Management (`/api/v1/admin/users`)
- `GET /api/v1/admin/users`: Paginated user list with query search (`q`), role filter, active status filter.
- `POST /api/v1/admin/users`: Provision new user. Automatically generates deterministic Feature 5 PID for students.
- `GET /api/v1/admin/users/{user_id}`: Full user detail drawer with enrolment history and activity metadata.
- `PUT /api/v1/admin/users/{user_id}/status`: Activate or suspend user. Enforces self-lockout and last-active-admin safeguards.
- `PUT /api/v1/admin/users/{user_id}/role`: Change user role. Enforces self-demotion and last-active-admin safeguards.
- `PUT /api/v1/admin/users/{user_id}/profile`: Update user profile details.

### Courses & Enrolments (`/api/v1/admin/courses`, `/api/v1/admin/enrolments`)
- `GET /api/v1/admin/courses`: Paginated courses list with lecturer details and enrolment counts.
- `PUT /api/v1/admin/courses/{course_id}/publish`: Toggle course publication state.
- `PUT /api/v1/admin/courses/{course_id}/lecturer`: Reassign course lecturer.
- `GET /api/v1/admin/enrolments`: Paginated enrolments list with course and status filters.
- `POST /api/v1/admin/enrolments`: Enrol a student into a course.
- `DELETE /api/v1/admin/enrolments/{enrolment_id}`: Soft unenrolment (marks status `withdrawn`; preserves grades/attendance/submissions).
- `POST /api/v1/admin/enrolments/bulk`: Idempotent bulk enrolment via CSV or student ID list with per-row results (`added`, `skipped`, `failed`).

### Consent & Ethics Governance (`/api/v1/admin/consent`)
- `GET /api/v1/admin/consent/coverage`: Consent coverage summary across active notice version.
- `GET /api/v1/admin/consent/notices`: Historical and current consent notices.
- `POST /api/v1/consent/notices`: Publish new consent notice version (semantic increment, markdown text).

### Pipeline & Ingestion (`/api/v1/pipeline`, `/api/v1/admin/ingestion`)
- `GET /api/v1/pipeline/runs`: List historical and active pipeline runs.
- `POST /api/v1/pipeline/trigger`: Trigger a new pipeline run for course and week (Admin only).
- `POST /api/v1/pipeline/runs/{course_id}/{week_index}/advance`: Advance pending run stages (Admin only).
- `GET /api/v1/pipeline/status`: APScheduler operational status and heartbeat.
- `GET /api/v1/admin/ingestion/status`: C1–C4 component ingestion health cards and acceptance rates.
- `GET /api/v1/admin/ingestion/runs`: Paginated historical ingestion batches.

### Privacy & Identity Vault (`/api/v1/admin/privacy`)
- `POST /api/v1/admin/privacy/reveal`: Break-glass identity reveal from PID to real identity. Requires justification >= 10 chars. Admin only.
- `GET /api/v1/admin/privacy/reveal-history`: Paginated history of break-glass reveal events.
- `POST /api/v1/admin/privacy/scrub-test`: Interactive PII scrubber test sandbox. Ephemeral; no logs recorded.

### Exports & Diagnostics (`/api/v1/admin/exports`, `/api/v1/admin/system`)
- `GET /api/v1/admin/exports/download`: Download processed datasets with consent filtering and CSV formula sanitization.
- `GET /api/v1/admin/exports/history`: Recent data export audit history.
- `GET /api/v1/admin/system/health`: DB connectivity, ping latency, contract schema version, OULAD metrics, and migrations list.

---

## 4. Role-Based Access Control (RBAC) Matrix

| Endpoint / Action | Admin | Auditor | Lecturer | Student | Counsellor |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Access Admin Console Layout (`/admin/*`) | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| View System Overview & KPIs | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| View Users Directory | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| Provision / Update Users & Roles | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| View Courses & Enrolments | Allowed | Allowed (Read) | Denied (403) | Denied (403) | Denied (403) |
| Mutate Courses (Publish, Lecturer) | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| Mutate Enrolments (Enrol, Soft Unenrol, Bulk) | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| View Consent Coverage & Notices | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| Publish New Consent Notice | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| View Audit Logs (`/admin/audit`) | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| View Pipeline Runs & Ingestion Health | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| Trigger Pipeline Run (`POST /pipeline/trigger`) | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| Advance Pipeline Run | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| Execute Break-Glass Identity Reveal | Allowed | Denied (403) | Denied (403) | Denied (403) | Denied (403) |
| View Break-Glass Reveal Audit History | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| Use PII Scrub Tester Sandbox | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| Download Datasets (CSV/JSON) | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |
| View System Health & Migrations | Allowed | Allowed | Denied (403) | Denied (403) | Denied (403) |

---

## 5. Audit Trail & Logged Actions

Every administrative mutation records an immutable entry in MongoDB `audit_logs` before returning success:

| Audit Action | Target Type | Target ID | Logged Details |
| :--- | :--- | :--- | :--- |
| `USER_CREATED` | `user` | New user UUID | `email`, `role`, `department` |
| `USER_STATUS_UPDATED` | `user` | Target user UUID | `is_active` (`old` vs `new`) |
| `USER_ROLE_UPDATED` | `user` | Target user UUID | `role` (`old` vs `new`) |
| `USER_PROFILE_UPDATED` | `user` | Target user UUID | Fields modified |
| `COURSE_UPDATED` | `course` | Course ID | `is_published` (`old` vs `new`) |
| `COURSE_LECTURER_ASSIGNED` | `course` | Course ID | `lecturer_id` (`old` vs `new`) |
| `STUDENT_ENROLLED` | `enrolment` | `course_id:pid` | `course_id`, `pid`, `enrolment_start` |
| `STUDENT_UNENROLLED` | `enrolment` | `course_id:pid` | `course_id`, `pid`, `action: soft_unenrol` |
| `CONSENT_NOTICE_PUBLISHED` | `consent_notice` | Version string | `old_version`, `new_version` |
| `PIPELINE_TRIGGERED` | `pipeline_run` | `course_id_wX` | `course_id`, `week_index`, `force` |
| `PIPELINE_RUN_STARTED` | `pipeline_run` | Run ID | `course_id`, `week_index`, `action: advance` |
| `IDENTITY_REVEAL` | `identity_vault` | PID | `reason`, `revealed_student_id` |
| `EXPORT_GENERATED` | `export` | Dataset key | `dataset`, `format`, `row_count`, `course_id`, `week_index` |

---

## 6. Security & Privacy Safeguards

1. **Zero Secrets in Network Payloads & Cache**:
   - Secrets (`secret_key`, `pseudonym_secret_key`, `component_api_keys`, `mongo_uri`) are NEVER returned in API responses or rendered in the DOM.
   - Component status displays boolean indicators (`"configured": true/false`) without key values.
2. **Break-Glass Identity Reveal Protection**:
   - Justification reason must be at least 10 characters long.
   - Revealed student identity is displayed in a one-time view modal and discarded upon dismissal. It is never persisted to browser local storage, session storage, or React Query cache.
3. **CSV Formula Injection Prevention**:
   - All exported CSV cells starting with formula trigger characters (`=`, `+`, `-`, `@`) are prepended with a single quote (`'`) to disable macro execution in Microsoft Excel and LibreOffice Calc.
4. **Consent-Gated Data Exports**:
   - Exports strictly query through the shared `build_export_filter` function, which aggregates consenting students under the active notice version and excludes students with `decision: "withdrawn"` or unaccepted notices.
5. **Administrative Self-Protection Safeguards**:
   - An administrator cannot deactivate their own account (HTTP 400).
   - An administrator cannot demote their own account role (HTTP 400).
   - The platform prevents deactivating or demoting the last remaining active administrator (HTTP 400).
6. **Ephemeral Scrub Sandbox**:
   - Interactive PII scrubbing runs stateless in-memory without audit logging or persistence.

---

## 7. Manual Test Verification Checklist

Follow this checklist during manual system demonstrations and examiner audits:

1. **RBAC Verification**:
   - [ ] Log in as `student` or `lecturer` -> Navigate to `/admin` -> Confirm redirection with 403 Forbidden.
   - [ ] Log in as `auditor` -> Navigate to `/admin` -> Confirm navigation sidebar displays view-only links; confirm `/admin/users` link is hidden.
   - [ ] As `auditor`, open `/admin/pipeline` -> Confirm "Trigger Run" and "Advance" buttons are absent or disabled; confirm calling `POST /api/v1/pipeline/trigger` returns 403.
   - [ ] As `auditor`, open `/admin/privacy` -> Confirm "Reveal Identity" button is disabled.

2. **User Administration & Safeguards**:
   - [ ] Log in as `admin` -> Open `/admin/users` -> Create new user with role `student`.
   - [ ] Verify that a deterministic PID `STU_xxxxxxxx` is derived in the Identity Vault.
   - [ ] Attempt to deactivate the currently logged-in admin user -> Confirm rejection with self-lockout warning.
   - [ ] Attempt to demote the sole active admin to `lecturer` -> Confirm rejection with last-admin protection warning.

3. **Courses & Enrolments Lifecycle**:
   - [ ] Open `/admin/courses` -> Toggle course `is_published` switch -> Verify immediate update and audit log entry.
   - [ ] Open `/admin/enrolments` -> Perform single student enrolment -> Verify student appears in active enrolments list.
   - [ ] Click "Unenrol" -> Confirm confirmation prompt -> Verify status transitions to `withdrawn` without deleting grades or attendance.
   - [ ] Click "Bulk Enrol" -> Upload CSV file with mix of new, already enrolled, and invalid student IDs -> Verify per-row results table (`added`, `skipped`, `failed`).

4. **Consent Governance**:
   - [ ] Open `/admin/consent` -> Review coverage metrics.
   - [ ] Click "Publish Notice Version" -> Enter new semantic version (e.g. `1.1.0`) and updated notice text -> Confirm publication.
   - [ ] Open `/admin/audit` -> Verify that `CONSENT_NOTICE_PUBLISHED` audit event is logged with old and new version.

5. **Break-Glass Privacy Reveal**:
   - [ ] Open `/admin/privacy` -> Enter an enrolled student's PID.
   - [ ] Enter justification with fewer than 10 characters -> Confirm button remains disabled.
   - [ ] Enter valid reason (>= 10 chars) -> Click "Reveal Identity" -> Confirm confirmation modal -> Inspect revealed identity.
   - [ ] Close modal -> Inspect React Query devtools / network cache -> Verify revealed identity is not cached.
   - [ ] Check reveal history table below -> Confirm `IDENTITY_REVEAL` entry with actor ID and justification.

6. **Dataset Export & Formula Sanitization**:
   - [ ] Open `/admin/exports` -> Select dataset `c1_messages` and format `CSV` -> Click Download.
   - [ ] Open downloaded CSV in text editor -> Verify cells with leading formulas are neutralized with `'`.
   - [ ] Open `/admin/audit` -> Confirm `EXPORT_GENERATED` audit log entry with dataset name and row count.
