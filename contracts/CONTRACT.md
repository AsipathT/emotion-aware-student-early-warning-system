# Data Contract Specification

**Version:** 1.0  
**Status:** Active  
**Scope:** Core LMS and Machine Learning Subsystems (C1, C2, C3, C4)

---

## 1. Overview & Architectural Principles

This document defines the formal data exchange contract between the Learning Management System (LMS) and four downstream Machine Learning components:
- **C1: Affective State Detection** (NLP distress detection and emotion classification)
- **C2: Behavioral Engagement Trajectory** (Clickstream telemetry and longitudinal time-series trends)
- **C3: Multimodal Risk Prediction** (Triangulated disengagement and dropout risk scoring)
- **C4: Adaptive Intervention Recommendation** (Cause-matched intervention ranking and outcome feedback)

### Architectural Invariants:
1. **Zero PII Transmission**: No identifying student data (institutional student IDs, full names, email addresses, or un-scrubbed raw text) may cross a component boundary. All student references are pseudonymized using Feature 5 Deterministic Pseudonyms (`Pid`).
2. **Strict Schema Conformance**: All payloads are validated using Pydantic v2 with `extra="forbid"`. Unexpected fields are rejected with HTTP 422, except during forward-compatible minor version upgrades where consumers gracefully ignore newly added optional fields (`extra="ignore"`).
3. **UTC Timezone Awareness**: All timestamps must be ISO 8601 UTC strings. Naive datetimes without timezone offset information are strictly rejected.

---

## 2. Naming Conventions & Version Distinction

> [!IMPORTANT]
> **Database Versioning vs. Contract Versioning**
> 
> - **Internal Storage Versioning**: Stored documents in MongoDB (such as Feature 7 audit log records or Feature 6 consent entries) use an integer field named `schema_version` (e.g. `1`, `2`) to manage local document migrations.
> - **Inter-Subsystem Contract Versioning**: The data contract defined here is tracked in application code as `CONTRACT_VERSION = "1.0"` (module `app.core.contract_version`). Inside the JSON transmission envelope, it is communicated in the `schema_version` field as a semantic `"major.minor"` string (e.g. `"1.0"`).

---

## 3. Generic Envelope (`Envelope[T]`)

Every HTTP message exchanged between the LMS and ML components must be wrapped in the standard `Envelope` structure:

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `schema_version` | `string` | Regex `^\d+\.\d+$` (e.g. `"1.0"`) | Yes | The contract specification version of the payload |
| `generated_at` | `string` | ISO 8601 UTC timestamp (`date-time`) | Yes | UTC timestamp recording when the payload was created |
| `source` | `string` | Enum: `lms`, `c1`, `c2`, `c3`, `c4` | Yes | Component or subsystem that generated the payload |
| `request_id` | `string` | Min length 1 (UUID recommended) | Yes | Correlation tracking ID matching HTTP `X-Request-ID` |
| `data` | `object` \| `array` | Single entity or list of entities | Yes | Strongly-typed contract payload entity |
| `page` | `integer` | $\ge 1$ | No | Current 1-indexed page number for list responses |
| `page_size` | `integer` | $1 \le \text{page\_size} \le 500$ | No | Number of records per page (max 500) |
| `total` | `integer` | $\ge 0$ | No | Total count of matching items across all pages |

---

## 4. Shared Common Types & Enums

### Primitives
- **`Pid`**: Pseudonymized Student Identifier (`string`, pattern `^STU_[0-9a-fA-F]{8}$`). Deterministically generated via HMAC-SHA256 (Feature 5).
- **`CourseId`**: Institutional course code (`string`, $1 \le \text{length} \le 128$).
- **`WeekIndex`**: Academic semester week index (`integer`, zero-based $\ge 0$).
- **`Score01`**: Normalized probability or confidence metric (`float`, $0.0 \le x \le 1.0$).
- **`CleanText`**: Scrubbed text sanitized against email addresses and registration IDs (`(?i)IT\d{8}`).

### Enumerations
- **`SourceType`**: `forum`, `chat`, `journal`
- **`DistressClass`**: `exam_anxiety`, `conceptual_confusion`, `academic_helplessness`, `course_frustration`, `motivation_erosion`
- **`TrajectoryLabel`**: `stable`, `improving`, `declining`, `volatile`
- **`RiskTier`**: `low`, `medium`, `high`, `critical`
- **`ComponentSource`**: `lms`, `c1`, `c2`, `c3`, `c4`
- **`Decision`**: `approved`, `modified`, `rejected`

---

## 5. Contract Schemas: LMS $\rightarrow$ Components (Outbound / Feature 21)

### 5.1 `TextMessageRecord` (LMS $\rightarrow$ C1)
Individual text interaction message extracted from LMS discussion boards, course chat rooms, or weekly learning journals.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `message_id` | `string` | Min length 1 | Yes | LMS internal unique communication message identifier |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `source_type` | `SourceType` | `forum`, `chat`, `journal` | Yes | Communication channel |
| `clean_text` | `CleanText` | Scrubbed text | Yes | PII-redacted student text |
| `timestamp` | `UtcDatetime` | ISO 8601 UTC | Yes | Time when the message was posted |
| `response_latency_seconds` | `float` | $\ge 0.0$ | No | Elapsed seconds before post/reply |
| `message_length_chars` | `integer` | $\ge 0$ | Yes | Character count of scrubbed text |
| `message_length_words` | `integer` | $\ge 0$ | Yes | Word count of scrubbed text |
| `reply_to_id` | `string` | Non-empty string | No | Parent message ID if part of a reply thread |

### 5.2 `BehaviorWeeklyRecord` (LMS $\rightarrow$ C2)
Weekly aggregated telemetry summarizing student activity across logins, video player interactions, and task submissions.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `login_count` | `integer` | $\ge 0$ | Yes | Number of distinct login sessions in week |
| `session_minutes` | `float` | $\ge 0.0$ | Yes | Total active duration on LMS (minutes) |
| `clicks` | `integer` | $\ge 0$ | Yes | Total interaction events (clicks, downloads) |
| `video_play_count` | `integer` | $\ge 0$ | Yes | Total lecture video play events |
| `video_pause_count` | `integer` | $\ge 0$ | Yes | Total video pause events |
| `video_rewind_count` | `integer` | $\ge 0$ | Yes | Total rewind / seek-back events |
| `video_skip_count` | `integer` | $\ge 0$ | Yes | Total skip / seek-forward events |
| `video_completion_pct` | `float` | $0.0 \le x \le 100.0$ | Yes | Mean lecture completion percentage |
| `submissions_count` | `integer` | $\ge 0$ | Yes | Total assignment/task submissions |
| `avg_submission_delay_hours` | `float` | Unbounded | Yes | Mean deadline offset in hours (negative = early, positive = late) |

### 5.3 `AcademicRecord` (LMS $\rightarrow$ C3)
Weekly academic milestone marks, continuous assessment grades, and attendance rates.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `ca_marks` | `float` | Cumulative mark | No | Continuous assessment marks to date |
| `midterm_mark` | `float` | Examination score | No | Midterm exam mark if evaluated |
| `quiz_scores` | `array[float]`| List of numbers | Yes | Scores for quizzes completed in this week |
| `attendance_pct` | `float` | $0.0 \le x \le 100.0$ | Yes | Semester-to-date attendance percentage |
| `submission_delay_hours` | `float` | Unbounded | Yes | Assignment submission offset relative to deadline |

---

## 6. Contract Schemas: Components $\rightarrow$ LMS (Inbound / Feature 23)

### 6.1 `AffectiveWeeklyVector` (C1 $\rightarrow$ LMS)
Aggregated affective distress classification and predictive confidence over a weekly observation window.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `emotion_scores` | `dict` | Keyed by 5 DistressClass, values $0.0 - 1.0$ | Yes | Probability distribution across all 5 distress types |
| `stress_label` | `CleanText` | Non-empty string | Yes | Dominant stress class label |
| `confidence` | `Score01` | $0.0 \le x \le 1.0$ | Yes | Confidence of model prediction |
| `message_count` | `integer` | $\ge 0$ | Yes | Number of messages evaluated in window |
| `top_drivers` | `array[TopDriver]` | Max 10 items | Yes | Linguistic tokens or markers and attribution weights |

### 6.2 `EngagementTrajectory` (C2 $\rightarrow$ LMS)
Behavioral time-series trend classification describing student engagement velocity.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `trajectory_label` | `TrajectoryLabel` | `stable`, `improving`, `declining`, `volatile` | Yes | Longitudinal trend classification |
| `confidence` | `Score01` | $0.0 \le x \le 1.0$ | Yes | Classification confidence score |
| `contributing_indicators` | `array[CleanText]` | Max 10 items | Yes | Key behavioral features driving classification |

### 6.3 `RiskAssessment` (C3 $\rightarrow$ LMS)
Synthesized multimodal risk score incorporating affective distress, behavioral velocity, and academic performance.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `course_id` | `CourseId` | Non-empty string | Yes | Course code |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `risk_score` | `Score01` | $0.0 \le x \le 1.0$ | Yes | Composite dropout / failure risk score |
| `risk_tier` | `RiskTier` | `low`, `medium`, `high`, `critical` | Yes | Actionable risk classification tier |
| `modality_contributions` | `ModalityContributions` | `affective`, `behavioral`, `academic` | Yes | Attribution breakdown summing to $1.0 \pm 0.01$ |
| `top_drivers` | `array[CleanText]` | Max 10 items | Yes | Top predictive factors across modalities |

### 6.4 `InterventionRecommendation` (C4 $\rightarrow$ LMS)
Ranked intervention candidate actions tailored to student risk profile.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `recommendation_id` | `string` | Min length 1 | Yes | Unique recommendation identifier |
| `pid` | `Pid` | `^STU_[0-9a-fA-F]{8}$` | Yes | Student pseudonym |
| `week_index` | `WeekIndex` | $\ge 0$ | Yes | Academic week index |
| `candidates` | `array[Candidate]` | 1 to 10 items | Yes | Ranked candidate interventions with unique consecutive ranks $1 \dots N$ |
| `status` | `CleanText` | Non-empty string | Yes | Operational status (e.g. `proposed`) |

### 6.5 `InterventionOutcome` (LMS $\rightarrow$ C4 Feedback)
Closed-loop operational evaluation of staff intervention delivery.

| Field | Type | Range / Format | Required? | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `recommendation_id` | `string` | Min length 1 | Yes | Reference to recommendation ID |
| `decision` | `Decision` | `approved`, `modified`, `rejected` | Yes | Staff decision on recommendation |
| `completed` | `boolean` | `true` / `false` | Yes | Whether intervention was completed |
| `observed_change` | `CleanText` | Max 500 chars | No | Brief post-intervention observation |
| `notes_present` | `boolean` | `true` / `false` | Yes | Flag indicating internal staff notes exist (raw text is prohibited) |

---

## 7. Versioning & Evolution Rules

Contracts evolve under semantic versioning principles (`major.minor`):

1. **Minor Version Bumps (e.g. 1.0 $\rightarrow$ 1.1)**:
   - Permitted changes: Adding optional fields with default values, adding ignorable non-breaking enum variants.
   - Compatibility rule: Consumers running on minor version 1.0 receiving a 1.1 payload MUST accept the payload and ignore unexpected fields (`extra="ignore"`).
   - Strict mode: Payloads presenting the same minor version (e.g. 1.0) strictly forbid unexpected fields (`extra="forbid"`).

2. **Major Version Bumps (e.g. 1.x $\rightarrow$ 2.0)**:
   - Breaking changes: Renaming fields, removing fields, altering data types, modifying numeric ranges or mathematical units, or changing semantics.
   - Deprecation and Transition: Major version updates require dual-support of the current and preceding major versions across a scheduled deprecation window.

---

## 8. Governance & Change Process

1. **Change Proposal**: Any proposed modification to contract schemas must be submitted via a dedicated Pull Request.
2. **Review & Approval**: The PR requires formal sign-off from all designated subsystem maintainers:
   - Core LMS Maintainer
   - C1 (Affective NLP) Maintainer
   - C2 (Behavioral Telemetry) Maintainer
   - C3 (Multimodal Risk) Maintainer
   - C4 (Intervention) Maintainer
3. **Schema Sync Verification**: All exported JSON schemas in `contracts/v1/` must be regenerated using `python scripts/export_contract_schemas.py`. CI validation (`tests/test_contract_schema_sync.py`) enforces schema file synchronization before any PR can be merged.

---

## 9. Changelog

- **v1.0 (2026-10-10)**: Initial formal release of Feature 24 data contract models, generic envelope, PII safety net, and schema synchronization tooling.
