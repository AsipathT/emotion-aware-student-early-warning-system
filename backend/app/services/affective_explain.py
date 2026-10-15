"""
backend/app/services/affective_explain.py

Feature 30: Explainable AI (XAI) root-cause heuristics and text highlighting.
Pure functions (no database I/O) implementing:
  - dominant_class: Identifies highest-scoring distress class and score.
  - week_over_week_change: Computes deltas between consecutive weeks.
  - build_rationale: Generates human-readable deterministic diagnostic explanations.
  - highlight_segments: Case-insensitive, non-overlapping whole-word phrase token highlighting.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

DISTRESS_LABELS: Dict[str, str] = {
    "exam_anxiety": "Exam Anxiety",
    "conceptual_confusion": "Conceptual Confusion",
    "academic_helplessness": "Academic Helplessness",
    "course_frustration": "Course Frustration",
    "motivation_erosion": "Motivation Erosion",
}


def dominant_class(emotion_scores: Optional[Dict[str, float]]) -> Tuple[str, float]:
    """
    Returns the (class_key, score) tuple for the highest-scoring distress class.
    Deterministic tie-breaking by class key.
    """
    if not emotion_scores:
        return ("none", 0.0)

    # Sort by score desc, then class_key asc
    sorted_classes = sorted(
        emotion_scores.items(),
        key=lambda item: (float(item[1]), item[0]),
        reverse=True,
    )
    top_class, top_score = sorted_classes[0]
    return (str(top_class), round(float(top_score), 4))


def week_over_week_change(
    prev_scores: Optional[Dict[str, float]],
    cur_scores: Dict[str, float],
) -> Dict[str, float]:
    """
    Calculates change in emotion scores compared to the preceding observation week.
    Returns delta dict: cur - prev.
    """
    if not cur_scores:
        return {}
    if not prev_scores:
        return {k: round(float(v), 4) for k, v in cur_scores.items()}

    deltas: Dict[str, float] = {}
    for k, v in cur_scores.items():
        prev_val = float(prev_scores.get(k, 0.0))
        deltas[k] = round(float(v) - prev_val, 4)
    return deltas


def build_rationale(
    week_doc: Dict[str, Any],
    prev_week_doc: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates a deterministic diagnostic explanation of the student's affective state.
    Uses templated heuristic rules without calling external LLMs.
    """
    emotion_scores = week_doc.get("emotion_scores") or {}
    top_class, top_score = dominant_class(emotion_scores)
    class_label = DISTRESS_LABELS.get(top_class, top_class.replace("_", " ").title())

    # Week-over-week delta
    change_str = ""
    if prev_week_doc and prev_week_doc.get("emotion_scores"):
        prev_scores = prev_week_doc["emotion_scores"]
        prev_score = float(prev_scores.get(top_class, 0.0))
        delta = top_score - prev_score
        if delta > 0.01:
            change_str = f", up {delta:.2f} from last week"
        elif delta < -0.01:
            change_str = f", down {abs(delta):.2f} from last week"
        else:
            change_str = ", steady compared to last week"
    else:
        change_str = ", initial observation"

    # Top linguistic drivers
    top_drivers = week_doc.get("top_drivers") or []
    driver_tokens: List[str] = []
    for d in top_drivers:
        tok = d.get("token_or_marker") or d.get("token")
        if tok and str(tok).strip():
            driver_tokens.append(f"'{str(tok).strip()}'")

    if driver_tokens:
        drivers_summary = f"Main language drivers: {', '.join(driver_tokens[:4])}."
    else:
        drivers_summary = "No prominent language markers detected."

    stress_label = str(week_doc.get("stress_label") or "moderate").capitalize()
    confidence = float(week_doc.get("confidence") or 0.0)

    return (
        f"Strongest signal this week: {class_label} ({top_score:.2f}{change_str}). "
        f"{drivers_summary} Overall status classified as {stress_label} with {confidence * 100:.0f}% confidence."
    )


def highlight_segments(
    text: str,
    drivers: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Splits text into non-overlapping segments with associated driver weights.
    Matches drivers case-insensitively using whole-word/phrase regex boundaries with re.escape.
    Returns: List of {'text': str, 'weight': float | None}
    """
    if not text:
        return []
    if not drivers:
        return [{"text": text, "weight": None}]

    # Filter and sort drivers by length descending so longer phrases take precedence
    valid_drivers: List[Tuple[str, float]] = []
    for d in drivers:
        tok = d.get("token_or_marker") or d.get("token")
        if tok and str(tok).strip():
            weight = float(d.get("weight", 0.0))
            valid_drivers.append((str(tok).strip(), weight))

    valid_drivers.sort(key=lambda x: len(x[0]), reverse=True)

    # Collect matched spans: (start, end, weight)
    candidate_spans: List[Tuple[int, int, float]] = []
    for token, weight in valid_drivers:
        prefix = r"\b" if re.match(r"^\w", token) else r""
        suffix = r"\b" if re.match(r".*\w$", token) else r""
        pattern = re.compile(prefix + re.escape(token) + suffix, re.IGNORECASE)

        for match in pattern.finditer(text):
            candidate_spans.append((match.start(), match.end(), weight))

    if not candidate_spans:
        return [{"text": text, "weight": None}]

    # Sort spans by start asc, then length desc
    candidate_spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))

    # Resolve overlapping spans (greedy non-overlapping selection)
    selected_spans: List[Tuple[int, int, float]] = []
    current_end = -1
    for start, end, weight in candidate_spans:
        if start >= current_end:
            selected_spans.append((start, end, weight))
            current_end = end

    # Build segments
    segments: List[Dict[str, Any]] = []
    cursor = 0
    for start, end, weight in selected_spans:
        if start > cursor:
            unmatched = text[cursor:start]
            if unmatched:
                segments.append({"text": unmatched, "weight": None})
        matched = text[start:end]
        if matched:
            segments.append({"text": matched, "weight": round(weight, 4)})
        cursor = end

    if cursor < len(text):
        remaining = text[cursor:]
        if remaining:
            segments.append({"text": remaining, "weight": None})

    return segments
