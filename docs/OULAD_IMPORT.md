# Open University Learning Analytics Dataset (OULAD) Import Tool

This document provides complete technical documentation for **Feature 26: OULAD Import Tool**, which ingests the Open University Learning Analytics Dataset into the LMS MongoDB Atlas collections.

---

## 1. Dataset Overview & Licensing

- **Authors**: Jakub Kuzilek, Martin Hlosta, and Zdenek Zdrahal (Knowledge Media Institute, The Open University, UK).
- **Publication**: *Scientific Data 4*, Article number: 170171 (2017). DOI: [10.1038/sdata.2017.171](https://doi.org/10.1038/sdata.2017.171).
- **License**: **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
- **Download Instructions**:
  The import tool **never** downloads data automatically over the internet.
  Users must download the official dataset manually from either:
  1. The Open University KMi Portal: [https://analyse.kmi.open.ac.uk/open_dataset](https://analyse.kmi.open.ac.uk/open_dataset)
  2. Kaggle Dataset: [https://www.kaggle.com/datasets/anlgrbz/student-demographics-online-education-dataoulad](https://www.kaggle.com/datasets/anlgrbz/student-demographics-online-education-dataoulad)

After extracting the archive, place the 7 CSV files into a local folder (e.g., `data/oulad/`).

---

## 2. File Manifest

The ingestion engine validates and expects the following 7 CSV files in the input directory:

| Filename | Description | Key Columns |
|---|---|---|
| `courses.csv` | Course modules and presentations | `code_module`, `code_presentation`, `module_presentation_length` |
| `vle.csv` | Virtual Learning Environment resources | `id_site`, `code_module`, `code_presentation`, `activity_type`, `week_from`, `week_to` |
| `studentRegistration.csv` | Student registrations and unregistrations | `code_module`, `code_presentation`, `id_student`, `date_registration`, `date_unregistration` |
| `studentInfo.csv` | Student demographics and final results | `code_module`, `code_presentation`, `id_student`, `final_result` (and demographic columns) |
| `assessments.csv` | Assessment metadata and weights | `code_module`, `code_presentation`, `id_assessment`, `assessment_type`, `date`, `weight` |
| `studentAssessment.csv` | Student submission scores and dates | `id_assessment`, `id_student`, `date_submitted`, `is_banked`, `score` |
| `studentVle.csv` | Student daily interaction click counts | `code_module`, `code_presentation`, `id_student`, `id_site`, `date`, `sum_click` |

---

## 3. Architecture & Mapping Specifications

### 3.1. Deterministic Pseudonymization (Zero PII Invariant)
- **Rule**: `pid = pseudonymize(f"oulad_{id_student}")` using the Feature 5 HMAC-SHA256 secret key.
- **Invariant**: The exact same student across multiple course presentations always receives the exact same PID.
- **Privacy Enforcement**: Raw OULAD student IDs are never logged to console, log files, or audit trails.
- **`identity_vault`**: Created with placeholder values:
  - `name`: `"OULAD Student"`
  - `email`: `"{pid.lower()}@oulad.placeholder"`
  - `is_imported`: `True`
  - `source`: `"oulad"`

### 3.2. Synthetic Calendar Anchor & Week Conversion
OULAD timestamps are integer day offsets relative to course presentation start dates.
- **Presentation Code Convention**:
  - Presentations ending in `B` (February intake): Anchor = `1 February <YEAR> 00:00:00 UTC`.
  - Presentations ending in `J` (October intake): Anchor = `1 October <YEAR> 00:00:00 UTC`.
  - Example: Presentation `2013J` anchors to `2013-10-01T00:00:00Z`.
- **Pre-Start Days Folding**:
  - In OULAD, preliminary interactions occur before course kickoff (e.g. day -14).
  - Formula: `week_index = max(0, day // 7)`.
  - All negative pre-start interactions safely fold into `week_index = 0`.
- **Records Beyond Course Length**:
  - Clamped to the presentation's final week `((module_presentation_length + 6) // 7) - 1`.
  - Counted and highlighted in the ingestion summary report.

### 3.3. Enrolments and Ground Truth Status
- **Status Mapping**:
  - `final_result == "Withdrawn"` $\rightarrow$ `status = "withdrawn"`.
  - `final_result in ["Pass", "Distinction", "Fail"]` $\rightarrow$ `status = "completed"`.
- **Ground Truth Fields**:
  - `final_result` is preserved as a ground truth string.
  - `unregistration_week = max(0, date_unregistration // 7)` when `date_unregistration` is provided.
  - Blank registration dates default `enrolment_start` to the presentation calendar anchor.

### 3.4. Assessments, Submissions, and Grades
- **Assessment Delay Calculation**:
  - `delay_hours = (date_submitted - assessment_date) * 24.0` (day precision).
  - Banked assessments (`is_banked == 1`) or assessments with blank dates (e.g. final exams) explicitly set `delay_hours = 0.0`.
- **Grades Key Invariant**:
  - Unique index on `(pid, course_id, assessment_id)`.
  - `week_index` is stored as an attribute for temporal querying, but is **not** part of the unique key.
  - This allows multiple assessments taken in the same calendar week to coexist without collision.

### 3.5. Activity Events (Telemetry Clickstream)
- **Aggregation**: If `studentVle.csv` contains multiple rows for the same `(pid, course_id, resource_id, day)`, the clicks are summed within the streaming chunk.
- **Deterministic ID**: `_id = sha256(f"{pid}_{course_id}_{resource_id}_{day}")[:24]`.
- **Bulk Insert**: Unordered `insert_many` with duplicate-key error handling allows safe, resumable ingestion.

### 3.6. Excluded Demographics
The following demographic attributes present in `studentInfo.csv` are **strictly prohibited** from analytics collections and are intentionally omitted:
- `gender`
- `region`
- `highest_education`
- `imd_band`
- `age_band`
- `num_of_prev_attempts`
- `studied_credits`
- `disability`

---

## 4. Feature 21 Consent Exemption Note

> [!NOTE]
> **Consent Policy Exemption for OULAD**:
> The OULAD dataset is public, anonymized research data released under CC BY 4.0.
> Unlike live LMS students, OULAD records **do not** have real human users who can sign an active consent agreement.
> **The Feature 21 longitudinal feature extractor and ML inference pipelines must treat records with `source="oulad"` as exempt from student consent filtering.**
> Do **not** create artificial consent records in `consent_records`.

---

## 5. CLI Usage & Examples

### 5.1. Dry-Run Validation
Inspects CSV files, verifies column headers, parses documents, and runs Pydantic / `$jsonSchema` validators without writing to MongoDB:
```powershell
docker compose exec backend python /scripts/import_oulad.py --dir /data/oulad --dry-run
```

### 5.2. Deterministic Sampling
Import a sample of 250 students with a fixed seed:
```powershell
docker compose exec backend python /scripts/import_oulad.py --dir /data/oulad --sample 250 --seed 42 --yes
```

### 5.3. Module Filtering
Import only specific modules (e.g. `AAA` and `BBB`):
```powershell
docker compose exec backend python /scripts/import_oulad.py --dir /data/oulad --modules AAA,BBB --yes
```

### 5.4. Full Dataset Ingestion
Stream and ingest all 7 CSV files with chunked reading of `studentVle.csv`:
```powershell
docker compose exec backend python /scripts/import_oulad.py --dir /data/oulad --chunk-size 50000 --yes
```

### 5.5. Rollback Mode
Safely remove all imported OULAD documents from target collections:
```powershell
docker compose exec backend python /scripts/import_oulad.py --remove-source oulad --yes
```
*Note: Audit logs and consent records are never deleted during rollback.*

---

## 6. Known Limitations of OULAD

When training or evaluating models with OULAD data, be aware of the following dataset boundaries:
1. **No Textual Content**: OULAD contains click counts on VLE resources and forums (`forumng`), but does **not** include forum message text or sentiment. Feature 24 Component 1 (`messages`, `affective_weekly`) cannot be directly derived from OULAD text.
2. **No Video Engagement Metrics**: Only aggregate resource clicks are available; no scrubbing, pauses, or watch percentages.
3. **No Attendance Tracking**: As a distance learning institution, there are no physical lecture attendance logs.
4. **No Intervention History**: OULAD contains final outcomes, but no operational records of teacher or counsellor interventions.
