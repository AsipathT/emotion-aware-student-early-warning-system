"""
backend/app/core/academic_derivation.py

Feature 21: Academic Record Derivation for Component 3 (Multimodal Risk Prediction).
There is no standalone 'academic_records' collection stored directly in MongoDB.
Instead, AcademicRecord envelopes are synthesized on demand by aggregating raw items
from:
  - 'grades' (continuous assessments & exam milestones)
  - 'attendance' (scheduled vs attended sessions)
  - 'submissions' (assignment turnaround & delay hours relative to deadline)
  - 'quiz_attempts' (formative weekly quiz scores)

════════════════════════════════════════════════════════════════════════════════
DERIVATION RULES & ASSUMPTIONS (Assumption: Confirm with the C3 Owner)
════════════════════════════════════════════════════════════════════════════════
1. ca_marks (Continuous Assessment):
   - Defined as the weight-normalized mean percentage of graded items that represent
     continuous assessments (assessment_type TMA, CMA, or CA; or grade_item containing
     TMA, CMA, or CA).
   - If items have configured weights (> 0), weights are used to compute the weighted mean:
     sum(percentage * weight) / sum(weight).
   - If no weights are specified, an arithmetic unweighted mean percentage is computed.
   - If no continuous assessment items were recorded in the week, returns null.
   [Assumption: Continuous assessments are identified by TMA/CMA/CA codes; confirm with C3 owner].

2. midterm_mark:
   - Evaluated as the percentage score for an assessment explicitly designated as
     'MIDTERM' (either in assessment_type or grade_item).
   - Returns null if no midterm examination was administered in this week
     (OULAD datasets have no midterm examinations).
   [Assumption: Midterms occur in specific scheduled weeks; null when absent; confirm with C3 owner].

3. quiz_scores:
   - An array containing the percentage scores (0.0 - 100.0) of all quiz attempts
     submitted by the student within this academic week.
   - Defaults to an empty list ([]) if no quiz attempts occurred.
   [Assumption: Quizzes evaluate formative mastery and multiple attempts are included; confirm with C3 owner].

4. attendance_pct:
   - Computed from attendance collection: (sessions_attended / sessions_scheduled) * 100.0,
     bounded between 0.0 and 100.0.
   - If sessions_scheduled is 0 (e.g. reading week or recess), defaults to 100.0%
     (no scheduled sessions were missed), or to the recorded attendance_pct if present.
   - If no attendance document exists for the student-week, defaults to 100.0%.
   [Assumption: Absence of scheduled sessions indicates full standing (100%); confirm with C3 owner].

5. submission_delay_hours:
   - Arithmetic mean of delay_hours across all submissions lodged by the student
     in this week relative to the assessment due date.
   - Negative numbers indicate early submissions (e.g. -4.5 = 4.5 hours ahead of deadline).
   - Positive numbers indicate late submissions.
   - Defaults to 0.0 if no submissions occurred in the week.
   [Assumption: Delay hours are computed relative to published deadlines; confirm with C3 owner].
════════════════════════════════════════════════════════════════════════════════
"""

from typing import Any, Dict, List, Optional

from app.schemas.contract.v1.c3_risk import AcademicRecord

# Recognized continuous assessment tags
CA_ASSESSMENT_TYPES = frozenset({"TMA", "CMA", "CA", "CONTINUOUS_ASSESSMENT", "CONTINUOUS ASSESSMENT"})


def _is_ca_item(asg_type: str, grade_item: str) -> bool:
    """Checks whether an assessment constitutes continuous assessment."""
    asg_upper = asg_type.upper().strip()
    if asg_upper in CA_ASSESSMENT_TYPES:
        return True

    item_upper = grade_item.upper().strip()
    if "MIDTERM" in item_upper or "EXAM" in item_upper:
        return False

    for tag in ("TMA", "CMA", "CA", "CONTINUOUS"):
        if tag in item_upper:
            return True

    return False


def _is_midterm_item(asg_type: str, grade_item: str) -> bool:
    """Checks whether an assessment constitutes a midterm examination."""
    asg_upper = asg_type.upper().strip()
    if asg_upper in {"MIDTERM", "MID_TERM", "MID-TERM"}:
        return True

    item_upper = grade_item.upper().strip()
    return "MIDTERM" in item_upper or "MID-TERM" in item_upper or "MID_TERM" in item_upper


def build_academic_record(
    pid: str,
    course_id: str,
    week_index: int,
    grades: Optional[List[Dict[str, Any]]] = None,
    attendance: Optional[Dict[str, Any]] = None,
    submissions: Optional[List[Dict[str, Any]]] = None,
    quiz_attempts: Optional[List[Dict[str, Any]]] = None,
    quizzes_map: Optional[Dict[str, Dict[str, Any]]] = None,
    assignments_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> AcademicRecord:
    """
    Synthesizes a strictly-validated AcademicRecord contract model for a given
    (pid, course_id, week_index) observation.
    """
    grades = grades or []
    submissions = submissions or []
    quiz_attempts = quiz_attempts or []
    quizzes_map = quizzes_map or {}
    assignments_map = assignments_map or {}

    # ── 1. Continuous Assessment & Midterm ─────────────────────────────────────
    ca_weighted_sum = 0.0
    ca_total_weight = 0.0
    ca_unweighted_sum = 0.0
    ca_count = 0

    midterm_score_pct: Optional[float] = None

    for g in grades:
        asg_id = str(g.get("assessment_id") or "").strip()
        asg_meta = assignments_map.get(asg_id, {})
        asg_type = str(asg_meta.get("assessment_type") or "")
        grade_item = str(g.get("grade_item") or "")

        score = float(g.get("score", 0.0))
        max_score = float(g.get("max_score", 100.0))
        if max_score <= 0.0:
            continue

        item_pct = (score / max_score) * 100.0

        # Check Midterm
        if _is_midterm_item(asg_type, grade_item):
            midterm_score_pct = round(item_pct, 2)

        # Check Continuous Assessment
        if _is_ca_item(asg_type, grade_item):
            weight = g.get("weight_pct")
            if weight is None and asg_meta:
                weight = asg_meta.get("weight")

            if weight is not None and float(weight) > 0.0:
                w_val = float(weight)
                ca_weighted_sum += item_pct * w_val
                ca_total_weight += w_val
            else:
                ca_unweighted_sum += item_pct

            ca_count += 1

    if ca_count == 0:
        ca_marks: Optional[float] = None
    elif ca_total_weight > 0.0:
        ca_marks = round(ca_weighted_sum / ca_total_weight, 2)
    else:
        ca_marks = round(ca_unweighted_sum / ca_count, 2)

    # ── 2. Quiz Scores ────────────────────────────────────────────────────────
    quiz_scores: List[float] = []
    for qa in quiz_attempts:
        qid = str(qa.get("quiz_id") or "").strip()
        q_meta = quizzes_map.get(qid, {})
        max_q_score = float(q_meta.get("max_score", 100.0)) if q_meta else 100.0
        score = float(qa.get("score", 0.0))

        if max_q_score > 0.0:
            q_pct = round((score / max_q_score) * 100.0, 2)
        else:
            q_pct = round(score, 2)
        quiz_scores.append(q_pct)

    # ── 3. Attendance Percentage ──────────────────────────────────────────────
    if attendance:
        scheduled = int(attendance.get("sessions_scheduled", 0))
        attended = int(attendance.get("sessions_attended", 0))
        if scheduled > 0:
            att_val = (attended / scheduled) * 100.0
        else:
            # Zero scheduled sessions: check pre-computed or default to 100%
            raw_att = attendance.get("attendance_pct")
            att_val = float(raw_att) if raw_att is not None else 100.0
    else:
        att_val = 100.0

    attendance_pct = round(min(100.0, max(0.0, att_val)), 2)

    # ── 4. Submission Delay Hours ─────────────────────────────────────────────
    if submissions:
        delays: List[float] = []
        for s in submissions:
            dh = s.get("delay_hours")
            if dh is not None:
                delays.append(float(dh))
        if delays:
            submission_delay_hours = round(sum(delays) / len(delays), 2)
        else:
            submission_delay_hours = 0.0
    else:
        submission_delay_hours = 0.0

    return AcademicRecord(
        pid=pid,
        course_id=course_id,
        week_index=week_index,
        ca_marks=ca_marks,
        midterm_mark=midterm_score_pct,
        quiz_scores=quiz_scores,
        attendance_pct=attendance_pct,
        submission_delay_hours=submission_delay_hours,
    )
