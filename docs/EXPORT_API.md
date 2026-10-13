# Feature 21: Component Data Export API Specification

**Version:** 1.0  
**Status:** Implemented  
**Scope:** LMS outbound endpoints to ML Components (C1, C2, C3)  
**Parent Contract:** [contracts/CONTRACT.md](../contracts/CONTRACT.md)

---

## 1. Overview & Architecture

The Component Export API provides read-only, secured, paginated, and pseudonymized HTTP endpoints for Machine Learning components:
- **Component 1 (Affective State Detection)**: Ingests student discussion text messages via `GET /api/v1/export/messages`.
- **Component 2 (Behavioral Engagement Trajectory)**: Ingests weekly engagement telemetry via `GET /api/v1/export/behavior`.
- **Component 3 (Multimodal Risk Prediction)**: Ingests derived weekly continuous assessment and attendance metrics via `GET /api/v1/export/academic`.

### Key Security & Privacy Invariants
1. **Zero Personally Identifiable Information (PII)**: Real student IDs (`student_id`), full names, email addresses, and registration numbers are strictly excluded. Only Feature 5 Pseudonym Identifiers (`STU_xxxxxxxx`) cross the component API boundary.
2. **Scrubbed Messages Only**: Discussion posts transmit `clean_text` exclusively. Any post failing automated PII safety net filters (e.g., residual email or `IT########` tokens) is dropped and counted in the audit record, never exported.
3. **Consent Gating**: Data is exported strictly if the student has actively accepted the current active consent notice (`col.CONSENT_RECORDS`). Anonymized public research data (`source == "oulad"`) is exempted from consent constraints.
4. **Mandatory Audit Logging**: Each export transaction is recorded in `col.AUDIT_LOGS` with `AuditAction.EXPORT_GENERATED`. Because data export is a critical regulatory action, the audit log write must succeed before the envelope is returned; failure aborts the request with `HTTP 500`.

---

## 2. Authentication & Authorization

All endpoints require either a component-specific secret key or an authenticated administrator session:

| Mechanism | Header Format | Description |
| :--- | :--- | :--- |
| **Component API Key** | `X-Component-Key: <secret_key>` | Scoped key matched using constant-time comparison (`hmac.compare_digest`). |
| **Admin Bearer Token** | `Authorization: Bearer <jwt_token>` | Valid JWT access token with role `admin` (intended for testing and health monitoring). |

### Component Key Configuration & Rotation
Component keys are configured on the LMS server in `.env` as a JSON string:
```bash
COMPONENT_API_KEYS={"c1": "c1_secret_key_prod", "c2": "c2_secret_key_prod", "c3": "c3_secret_key_prod"}
```
- **Scope Isolation**: Key `c1` can access only `/messages`. Using `c1` on `/behavior` or `/academic` returns `HTTP 403 Forbidden`.
- **Key Rotation**: To rotate a key, update the value in `.env` and reload the LMS service. Old keys immediately become invalid (`HTTP 401 Unauthorized`).
- **Unconfigured Keys**: If `COMPONENT_API_KEYS` is empty or unconfigured, all export routes return `HTTP 503 Service Unavailable`.

---

## 3. Endpoints & Query Parameters

All export endpoints reside under `/api/v1/export` and support the following query parameters:

| Parameter | Type | Required? | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `course_id` | `string` | No | `null` | Institutional course identifier (e.g. `CS101`, `DEMO101`). |
| `week_from` | `integer` | No | `null` | Starting academic week index (inclusive, $\ge 0$). |
| `week_to` | `integer` | No | `null` | Ending academic week index (inclusive, $\ge 0$). |
| `pid` | `string` | No | `null` | Pseudonymized student ID (`STU_[0-9a-f]{8}`). |
| `page` | `integer` | No | `1` | 1-based page index ($\ge 1$). |
| `page_size` | `integer` | No | `100` | Number of items per page ($1 \le \text{page\_size} \le 500$). |

---

## 4. Endpoint Specifications

### 4.1. Component 1: `GET /api/v1/export/messages`
Serves discussion forums, chat logs, and reflective learning journals.

- **Required Scope:** `c1`
- **Output Record:** `TextMessageRecord`
- **Stable Sort Order:** `course_id ASC`, `week_index ASC`, `pid ASC`, `timestamp ASC`

#### Sample Response
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-11T12:00:00Z",
  "source": "lms",
  "request_id": "7b0d1e3a-7182-4217-9c9e-5b123456789a",
  "data": [
    {
      "message_id": "MSG_STU_4816cfbc_DEMO101_W0",
      "pid": "STU_4816cfbc",
      "course_id": "DEMO101",
      "week_index": 0,
      "source_type": "forum",
      "clean_text": "The lecture examples for algorithmic sorting were very clear and practical.",
      "timestamp": "2026-09-03T09:00:00Z",
      "response_latency_seconds": 120.0,
      "message_length_chars": 73,
      "message_length_words": 10,
      "reply_to_id": null
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

---

### 4.2. Component 2: `GET /api/v1/export/behavior`
Serves weekly clickstream interactions and video playback telemetry.

- **Required Scope:** `c2`
- **Output Record:** `BehaviorWeeklyRecord`
- **Stable Sort Order:** `course_id ASC`, `week_index ASC`, `pid ASC`

#### Sample Response
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-11T12:00:00Z",
  "source": "lms",
  "request_id": "9c1e2f4b-8293-5328-ad0f-6c234567890b",
  "data": [
    {
      "pid": "STU_4816cfbc",
      "course_id": "DEMO101",
      "week_index": 0,
      "login_count": 5,
      "session_minutes": 180.0,
      "clicks": 45,
      "video_play_count": 6,
      "video_pause_count": 4,
      "video_rewind_count": 2,
      "video_skip_count": 1,
      "video_completion_pct": 88.5,
      "submissions_count": 1,
      "avg_submission_delay_hours": -3.5
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

---

### 4.3. Component 3: `GET /api/v1/export/academic`
Serves derived continuous assessment percentages, midterm marks, quiz scores, and attendance rates synthesized across grades, attendance, quizzes, and submissions.

- **Required Scope:** `c3`
- **Output Record:** `AcademicRecord`
- **Stable Sort Order:** `course_id ASC`, `week_index ASC`, `pid ASC`

#### Academic Derivation Rules & Assumptions
*(Assumption: Confirm with the Component 3 owner)*

1. **`ca_marks`**: Computed as the weight-normalized mean percentage of graded continuous assessment items (`TMA`, `CMA`, `CA`). If items have configured weights, weighted mean $\frac{\sum (\% \times w)}{\sum w}$ is computed. If no continuous assessments were completed that week, returns `null`.
2. **`midterm_mark`**: Score percentage of an assessment explicitly tagged as `MIDTERM`. Returns `null` if no midterm was administered in that week.
3. **`quiz_scores`**: Array of percentage scores ($0.0 - 100.0$) for all quiz attempts submitted in the week. Defaults to `[]` if none were taken.
4. **`attendance_pct`**: Computed from sessions: $\min\left(100.0, \frac{\text{attended}}{\text{scheduled}} \times 100.0\right)$. If zero sessions were scheduled (e.g. reading week), defaults to $100.0\%$.
5. **`submission_delay_hours`**: Mean deadline offset across submissions lodged in that week. Negative values represent early submissions (e.g. $-2.5$ hours); positive values denote late submissions. Defaults to $0.0$ if none were lodged.

#### Sample Response
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-11T12:00:00Z",
  "source": "lms",
  "request_id": "1d2e3f4a-9304-6439-be1a-7d345678901c",
  "data": [
    {
      "pid": "STU_4816cfbc",
      "course_id": "DEMO101",
      "week_index": 0,
      "ca_marks": 82.0,
      "midterm_mark": null,
      "quiz_scores": [90.0],
      "attendance_pct": 100.0,
      "submission_delay_hours": -2.5
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

---

## 5. Error Codes & Handling

| HTTP Code | Condition | Audit Outcome |
| :--- | :--- | :--- |
| **`400 Bad Request`** | Invalid PID syntax, invalid `risk_tier`, invalid `ingested_since`, or `week_from > week_to`. | Not audited |
| **`401 Unauthorized`** | Missing `X-Component-Key` header, or key does not match any configured component. | `ACCESS_DENIED` |
| **`403 Forbidden`** | Valid component key provided for an unauthorized scope (e.g. C1 key calling `/affective`). | `ACCESS_DENIED` |
| **`422 Unprocessable Content`** | Pydantic validation failure (e.g. `page_size > 500`). | Not audited |
| **`500 Internal Server Error`** | Critical audit log persistence failure. Export is aborted to maintain regulatory compliance. | Critical failure |
| **`503 Service Unavailable`** | `COMPONENT_API_KEYS` is unconfigured on the LMS server. | System warning |

---

## 6. Component Read-Back Endpoints (Pipeline Inter-Component Sharing)

Downstream ML components frequently require access to intermediate inference results generated by earlier components in the pipeline. Instead of peer-to-peer coupling, the LMS serves as the centralized, strictly audited, consent-gated hub:
- **Component 3 (Multimodal Risk Prediction)** reads:
  - C1 weekly emotion probability vectors via `GET /api/v1/export/affective`
  - C2 weekly behavioral trajectories via `GET /api/v1/export/trajectory`
- **Component 4 (Adaptive Interventions)** reads:
  - C1 weekly emotion probability vectors via `GET /api/v1/export/affective`
  - C2 weekly behavioral trajectories via `GET /api/v1/export/trajectory`
  - C3 multimodal risk predictions via `GET /api/v1/export/risk`
  - Staff intervention review decisions & observed outcomes via `GET /api/v1/export/outcomes`

### 6.1 Complete Authorization & Scopes Matrix

| Endpoint | Path | Authorized Component Scopes | Output Model |
| :--- | :--- | :--- | :--- |
| **LMS Raw Messages** | `GET /api/v1/export/messages` | `c1` | `Envelope[List[TextMessageRecord]]` |
| **LMS Telemetry** | `GET /api/v1/export/behavior` | `c2` | `Envelope[List[BehaviorWeeklyRecord]]` |
| **LMS Academic Marks** | `GET /api/v1/export/academic` | `c3` | `Envelope[List[AcademicRecord]]` |
| **C1 Affective Read-Back** | `GET /api/v1/export/affective` | `c3`, `c4` | `Envelope[List[AffectiveWeeklyVector]]` |
| **C2 Trajectory Read-Back** | `GET /api/v1/export/trajectory` | `c3`, `c4` | `Envelope[List[EngagementTrajectory]]` |
| **C3 Risk Read-Back** | `GET /api/v1/export/risk` | `c4` | `Envelope[List[RiskAssessment]]` |
| **Staff Outcomes Read-Back**| `GET /api/v1/export/outcomes` | `c4` | `Envelope[List[InterventionOutcome]]` |

*Note: Administrator Bearer tokens (`Authorization: Bearer <jwt>`) are valid across all 7 endpoints for monitoring and testing.*

### 6.2 Query Parameters & Filtering

| Parameter | Type | Endpoints | Description |
| :--- | :--- | :--- | :--- |
| `course_id` | `string` | `/affective`, `/trajectory`, `/risk` | Filter records by institutional course identifier |
| `week_from` | `integer` | `/affective`, `/trajectory`, `/risk` | Inclusive starting academic week index ($\ge 0$) |
| `week_to` | `integer` | `/affective`, `/trajectory`, `/risk` | Inclusive ending academic week index ($\ge 0$) |
| `pid` | `string` | `/affective`, `/trajectory`, `/risk` | Filter by student pseudonym (`STU_xxxxxxxx`) |
| `risk_tier` | `string` | `/risk` | Categorical risk filter (`low`, `medium`, `high`, `critical`) |
| `recommendation_id` | `string` | `/outcomes` | Filter outcomes for a specific recommendation ID |
| `ingested_since` | `string` | `/affective`, `/trajectory`, `/risk`, `/outcomes` | UTC timestamp in ISO 8601 format (e.g. `2026-10-12T00:00:00Z`). Used for incremental delta polling. Backed by MongoDB indexes on `ingested_at`. |
| `page` | `integer` | All | 1-based page number (default: `1`) |
| `page_size` | `integer` | All | Records per page (default: `100`, max: `500`) |

### 6.3 Consent Gating & Anonymization Rules

1. **Student Level Consent**: Records are exported only for students whose latest recorded decision for the active consent notice version is `"accepted"`, or whose identities originate from OULAD research data (`source == "oulad"` or `is_imported == true`).
2. **Revocation Enforced**: When a student withdraws consent (`"withdrawn"`), they are immediately excluded from all export queries.
3. **Outcomes Linking Rule**: `InterventionOutcome` records contain no PID directly. The LMS joins each outcome to `col.RECOMMENDATIONS` by `recommendation_id`. Outcomes associated with recommendations for students who have not consented (or whose recommendations do not exist) are omitted and counted in `skipped_count`.
4. **Empty Outcomes Handling**: If academic staff have not yet reviewed or recorded outcomes for proposed interventions, `GET /api/v1/export/outcomes` returns `HTTP 200` with `data: []` and `total: 0`. It does not fail or error.
5. **PII Safety Net**: All text fields (`stress_label`, `top_drivers`, `contributing_indicators`, `observed_change`) are dynamically scanned for email addresses and institutional registration IDs (`IT########`). Contaminated records are scrubbed from the output and audited in `skipped_count`.

### 6.4 Sample Read-Back Responses

#### `GET /api/v1/export/affective` (C3 / C4)
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-12T00:00:00Z",
  "source": "lms",
  "request_id": "4b61fa2e-5036-4071-8b01-fce8995a1204",
  "data": [
    {
      "pid": "STU_cdbe990a",
      "course_id": "CS101",
      "week_index": 2,
      "emotion_scores": {
        "exam_anxiety": 0.45,
        "conceptual_confusion": 0.70,
        "academic_helplessness": 0.15,
        "course_frustration": 0.30,
        "motivation_erosion": 0.20
      },
      "stress_label": "conceptual_confusion",
      "confidence": 0.88,
      "message_count": 6,
      "top_drivers": [
        {"token_or_marker": "recursion confusion", "weight": 0.75}
      ]
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

#### `GET /api/v1/export/risk` (C4)
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-12T00:00:00Z",
  "source": "lms",
  "request_id": "8f1a23c4-1294-4328-98e1-51239abcef12",
  "data": [
    {
      "pid": "STU_cdbe990a",
      "course_id": "CS101",
      "week_index": 2,
      "risk_score": 0.72,
      "risk_tier": "high",
      "modality_contributions": {
        "affective": 0.40,
        "behavioral": 0.35,
        "academic": 0.25
      },
      "top_drivers": ["drop_in_submissions", "high_course_frustration"]
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

#### `GET /api/v1/export/outcomes` (C4)
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-12T00:00:00Z",
  "source": "lms",
  "request_id": "99c812ad-0012-4211-9a73-67890bcdef34",
  "data": [
    {
      "recommendation_id": "REC_STU_cdbe990a_W2",
      "decision": "approved",
      "completed": true,
      "observed_change": "Student attended peer mentoring session and submitted backlog lab",
      "notes_present": false
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

