"""
backend/app/importers/oulad/mappings.py

Feature 26: Canonical OULAD-to-LMS Mapping Rules.
All mapping logic, calendar calculations, and pseudonym transformations are
documented and implemented in this single source of truth.

Key Invariants:
1. Pseudonymization: Deterministic HMAC-SHA256 hash using Feature 5 core privacy layer.
   Format: STU_xxxxxxxx. Raw student IDs and PID mappings are never logged.
2. Zero PII in Analytics: Demographics (gender, region, highest_education, imd_band,
   age_band, num_of_prev_attempts, studied_credits, disability) are strictly excluded.
3. Synthetic Calendar Anchor: Presentation starts Feb 1 (B) or Oct 1 (J) of code year at 00:00 UTC.
4. Pre-Start Day Folding: Negative days fold into week 0 via max(0, day // 7).
5. Ground Truth Status: final_result preserved, status mapped to 'withdrawn' or 'completed'.
6. Banked Assessments: Submissions marked is_banked=True have delay_hours=0.0.
7. Grades Key: Unique on (pid, course_id, assessment_id) with week_index stored as a field.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.core.privacy import is_valid_pid, pseudonymize

# ── Excluded Demographic Attributes ───────────────────────────────────────────
EXCLUDED_DEMOGRAPHIC_FIELDS: Tuple[str, ...] = (
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "num_of_prev_attempts",
    "studied_credits",
    "disability",
)

SOURCE_TAG = "oulad"
PRESENTATION_CODE_REGEX = re.compile(r"^(\d{4})([A-Za-z])$")


# ── 1. Pseudonymization ───────────────────────────────────────────────────────

def oulad_pid(id_student: Union[str, int]) -> str:
    """
    Derives deterministic Feature 5 student pseudonym: STU_xxxxxxxx.
    Prefixes 'oulad_' to raw student ID to avoid namespace collisions.
    Raw student ID is never logged or exposed.
    """
    cleaned_id = str(id_student).strip()
    pid = pseudonymize(f"oulad_{cleaned_id}")
    if not is_valid_pid(pid):
        raise ValueError(f"Generated PID '{pid}' does not adhere to Feature 5 format.")
    return pid


# ── 2. Synthetic Calendar Anchors ─────────────────────────────────────────────

def calculate_calendar_anchor(code_presentation: str) -> datetime:
    """
    Calculates synthetic calendar anchor for an OULAD presentation:
      - Presentations ending in 'B' start on February 1 of the presentation year at 00:00 UTC.
      - Presentations ending in 'J' start on October 1 of the presentation year at 00:00 UTC.
    Example: '2013J' -> 2013-10-01 00:00:00+00:00
             '2014B' -> 2014-02-01 00:00:00+00:00
    """
    cleaned = str(code_presentation).strip().upper()
    match = PRESENTATION_CODE_REGEX.match(cleaned)
    if not match:
        # Fallback for unexpected presentations: assume current year, October
        year = int(cleaned[:4]) if len(cleaned) >= 4 and cleaned[:4].isdigit() else datetime.now(timezone.utc).year
        suffix = cleaned[-1] if cleaned else "J"
    else:
        year = int(match.group(1))
        suffix = match.group(2)

    month = 2 if suffix == "B" else 10
    return datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)


def day_to_timestamp(anchor: datetime, day_offset: int) -> datetime:
    """Computes exact UTC timestamp at 00:00:00 for a given day offset."""
    return anchor + timedelta(days=int(day_offset))


def day_to_week(day_offset: int, presentation_length: Optional[int] = None) -> Tuple[int, bool]:
    """
    Converts day offset to zero-indexed week_index:
      - Negative (pre-start) days fold into week 0: max(0, day // 7).
      - If presentation_length is known, clamps to maximum week index.
    Returns:
      (week_index, is_clamped_beyond_course_length)
    """
    raw_week = int(day_offset) // 7
    week_index = max(0, raw_week)

    is_beyond = False
    if presentation_length is not None and presentation_length > 0:
        max_week = max(0, (int(presentation_length) + 6) // 7 - 1)
        if week_index > max_week:
            week_index = max_week
            is_beyond = True

    return week_index, is_beyond


# ── 3. Enrolment & Outcome Mapping ────────────────────────────────────────────

def map_enrolment_status(final_result: Optional[str]) -> str:
    """
    Maps OULAD final_result to LMS enrolment status:
      - 'Withdrawn' -> 'withdrawn'
      - 'Pass', 'Distinction', 'Fail' -> 'completed'
    """
    if final_result and str(final_result).strip().lower() == "withdrawn":
        return "withdrawn"
    return "completed"


# ── 4. Assessment Delay & Banked Calculation ──────────────────────────────────

def calculate_delay_hours(
    date_submitted: Optional[Union[int, str]],
    assessment_date: Optional[Union[int, str]],
    is_banked: bool = False,
) -> float:
    """
    Calculates submission delay in hours:
      delay_hours = (date_submitted - assessment_date) * 24.0
    Day precision is noted.
    If is_banked is True, or assessment_date is blank, delay_hours = 0.0.
    """
    if is_banked:
        return 0.0

    if date_submitted in (None, "") or assessment_date in (None, ""):
        return 0.0

    try:
        sub_day = int(date_submitted)
        due_day = int(assessment_date)
        return float((sub_day - due_day) * 24.0)
    except (ValueError, TypeError):
        return 0.0


# ── 5. Deterministic Hash for Activity Events ─────────────────────────────────

def generate_activity_event_id(pid: str, course_id: str, resource_id: str, day: int) -> str:
    """
    Generates deterministic MongoDB _id for activity events based on
    (pid, course_id, resource_id, day). Ensures idempotency and deduplication.
    """
    payload = f"{pid}_{course_id}_{resource_id}_{day}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


# ── 6. Storage Document Builders ──────────────────────────────────────────────

def build_identity_vault_doc(id_student: Union[str, int], run_id: str) -> Dict[str, Any]:
    """
    Constructs an identity_vault entry for an OULAD student with placeholder
    metadata and zero real PII.
    """
    pid = oulad_pid(id_student)
    now = datetime.now(timezone.utc)
    return {
        "_id": f"vault_{pid}",
        "pid": pid,
        "student_id": f"OULAD_{id_student}",
        "name": "OULAD Student",
        "email": f"{pid.lower()}@oulad.placeholder",
        "is_imported": True,
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }


def build_course_doc(
    code_module: str,
    code_presentation: str,
    presentation_length: int,
    run_id: str,
) -> Dict[str, Any]:
    """Constructs a course document from courses.csv."""
    course_id = f"{code_module}_{code_presentation}"
    now = datetime.now(timezone.utc)
    return {
        "_id": f"course_{course_id}",
        "course_id": course_id,
        "title": f"OULAD Course {code_module} ({code_presentation})",
        "description": f"OULAD module {code_module}, presentation {code_presentation} ({presentation_length} days)",
        "lecturer_id": None,
        "is_published": True,
        "presentation_length_days": int(presentation_length),
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "created_at": now,
        "updated_at": now,
    }


def build_course_week_docs(
    code_module: str,
    code_presentation: str,
    presentation_length: int,
    run_id: str,
) -> List[Dict[str, Any]]:
    """Generates course_weeks documents spanning the presentation length."""
    course_id = f"{code_module}_{code_presentation}"
    anchor = calculate_calendar_anchor(code_presentation)
    num_weeks = max(1, (int(presentation_length) + 6) // 7)
    now = datetime.now(timezone.utc)

    weeks: List[Dict[str, Any]] = []
    for w in range(num_weeks):
        start_date = anchor + timedelta(days=w * 7)
        end_date = anchor + timedelta(days=(w + 1) * 7)
        weeks.append({
            "_id": f"cw_{course_id}_{w}",
            "course_id": course_id,
            "week_index": w,
            "title": f"Week {w}",
            "start_date": start_date,
            "end_date": end_date,
            "source": SOURCE_TAG,
            "ingestion_run_id": run_id,
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })
    return weeks


def build_enrolment_doc(
    code_module: str,
    code_presentation: str,
    id_student: Union[str, int],
    date_registration: Optional[Union[str, int]],
    date_unregistration: Optional[Union[str, int]],
    final_result: Optional[str],
    run_id: str,
) -> Dict[str, Any]:
    """Constructs an enrolment document joining registration and info data."""
    course_id = f"{code_module}_{code_presentation}"
    pid = oulad_pid(id_student)
    anchor = calculate_calendar_anchor(code_presentation)
    now = datetime.now(timezone.utc)

    # Registration date handling (blank -> anchor)
    reg_day = int(date_registration) if date_registration not in (None, "") else None
    enrolment_start = anchor + timedelta(days=reg_day) if reg_day is not None else anchor

    # Unregistration date handling
    unreg_day = int(date_unregistration) if date_unregistration not in (None, "") else None
    enrolment_end = anchor + timedelta(days=unreg_day) if unreg_day is not None else None
    unreg_week = max(0, unreg_day // 7) if unreg_day is not None else None

    status = map_enrolment_status(final_result)

    return {
        "_id": f"enr_{course_id}_{pid}",
        "pid": pid,
        "course_id": course_id,
        "enrolment_start": enrolment_start,
        "status": status,
        "enrolment_end": enrolment_end,
        "final_result": str(final_result).strip() if final_result else None,
        "unregistration_week": unreg_week,
        "date_registration": reg_day,
        "date_unregistration": unreg_day,
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }


def build_assignment_doc(
    code_module: str,
    code_presentation: str,
    id_assessment: Union[str, int],
    assessment_type: str,
    date: Optional[Union[str, int]],
    weight: Optional[Union[str, float]],
    presentation_length: int,
    run_id: str,
) -> Dict[str, Any]:
    """Constructs an assignment document from assessments.csv."""
    course_id = f"{code_module}_{code_presentation}"
    assessment_id = str(id_assessment).strip()
    anchor = calculate_calendar_anchor(code_presentation)
    now = datetime.now(timezone.utc)

    # Date handling: if blank (e.g. exams), set due_date to course end
    if date not in (None, ""):
        due_day = int(date)
    else:
        due_day = int(presentation_length)

    week_index, _ = day_to_week(due_day, presentation_length)
    due_date = anchor + timedelta(days=due_day)
    parsed_weight = float(weight) if weight not in (None, "") else 0.0

    return {
        "_id": f"asg_{course_id}_{assessment_id}",
        "assignment_id": assessment_id,
        "course_id": course_id,
        "week_index": week_index,
        "title": f"{assessment_type} {assessment_id}",
        "due_date": due_date,
        "max_points": 100.0,
        "assessment_type": str(assessment_type).strip(),
        "weight": parsed_weight,
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }


def build_submission_doc(
    code_module: str,
    code_presentation: str,
    id_assessment: Union[str, int],
    id_student: Union[str, int],
    date_submitted: Optional[Union[str, int]],
    is_banked: Optional[Union[str, int, bool]],
    score: Optional[Union[str, float]],
    assessment_date: Optional[Union[str, int]],
    run_id: str,
) -> Dict[str, Any]:
    """Constructs a submission document from studentAssessment.csv."""
    course_id = f"{code_module}_{code_presentation}"
    assessment_id = str(id_assessment).strip()
    pid = oulad_pid(id_student)
    anchor = calculate_calendar_anchor(code_presentation)
    now = datetime.now(timezone.utc)

    sub_day = int(date_submitted) if date_submitted not in (None, "") else 0
    submitted_at = anchor + timedelta(days=sub_day)

    banked_bool = bool(int(is_banked)) if is_banked not in (None, "") else False
    delay_hours = calculate_delay_hours(sub_day, assessment_date, banked_bool)

    parsed_score = float(score) if score not in (None, "") else None

    return {
        "_id": f"sub_{course_id}_{assessment_id}_{pid}",
        "submission_id": f"{course_id}_{assessment_id}_{pid}",
        "assignment_id": assessment_id,
        "pid": pid,
        "course_id": course_id,
        "submitted_at": submitted_at,
        "score": parsed_score,
        "feedback": None,
        "is_banked": banked_bool,
        "delay_hours": delay_hours,
        "date_submitted": sub_day,
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }


def build_grade_doc(
    code_module: str,
    code_presentation: str,
    id_assessment: Union[str, int],
    id_student: Union[str, int],
    date_submitted: Optional[Union[str, int]],
    score: Optional[Union[str, float]],
    weight: Optional[Union[str, float]],
    assessment_date: Optional[Union[str, int]],
    presentation_length: int,
    run_id: str,
) -> Dict[str, Any]:
    """
    Constructs a grade document from studentAssessment.csv.
    Key invariant: unique on (pid, course_id, assessment_id); week_index is a field.
    """
    course_id = f"{code_module}_{code_presentation}"
    assessment_id = str(id_assessment).strip()
    pid = oulad_pid(id_student)
    now = datetime.now(timezone.utc)

    # Determine week_index from submission date, fallback to assessment due date
    if date_submitted not in (None, ""):
        sub_day = int(date_submitted)
    elif assessment_date not in (None, ""):
        sub_day = int(assessment_date)
    else:
        sub_day = 0

    week_index, _ = day_to_week(sub_day, presentation_length)

    # Parse score and weight
    parsed_score = float(score) if score not in (None, "") and float(score) >= 0.0 else 0.0
    parsed_weight = float(weight) if weight not in (None, "") else None

    return {
        "_id": f"grd_{course_id}_{assessment_id}_{pid}",
        "pid": pid,
        "course_id": course_id,
        "week_index": week_index,
        "grade_item": f"Assessment {assessment_id}",
        "score": parsed_score,
        "max_score": 100.0,
        "weight_pct": parsed_weight,
        "assessment_id": assessment_id,
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }


def build_activity_event_doc(
    code_module: str,
    code_presentation: str,
    id_student: Union[str, int],
    id_site: Union[str, int],
    day: int,
    sum_click: int,
    activity_type: str,
    presentation_length: int,
    run_id: str,
) -> Tuple[Dict[str, Any], bool]:
    """
    Constructs an activity_events telemetry document.
    Deterministic _id prevents duplicate writes on retry.
    Returns:
      (document, is_clamped_beyond_course_length)
    """
    course_id = f"{code_module}_{code_presentation}"
    pid = oulad_pid(id_student)
    site_id = str(id_site).strip()
    anchor = calculate_calendar_anchor(code_presentation)
    now = datetime.now(timezone.utc)

    timestamp = day_to_timestamp(anchor, day)
    week_index, is_beyond = day_to_week(day, presentation_length)
    event_id = generate_activity_event_id(pid, course_id, site_id, day)

    doc = {
        "_id": event_id,
        "pid": pid,
        "course_id": course_id,
        "week_index": week_index,
        "timestamp": timestamp,
        "event_type": str(activity_type).strip() if activity_type else "resource",
        "event_payload": {
            "id_site": site_id,
            "clicks": int(sum_click),
            "timestamp_precision": "day",
        },
        "timestamp_precision": "day",
        "resource_id": site_id,
        "clicks": int(sum_click),
        "source": SOURCE_TAG,
        "ingestion_run_id": run_id,
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }
    return doc, is_beyond
