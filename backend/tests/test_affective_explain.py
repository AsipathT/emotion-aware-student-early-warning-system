"""
backend/tests/test_affective_explain.py

Unit tests for pure functions in Feature 30:
- dominant_class (tie-breaking, score selection)
- week_over_week_change (delta calculations)
- build_rationale (diagnostic templates)
- highlight_segments (case-insensitive, whole-word/phrase, non-overlapping)

Pure unit tests only. No database connection or I/O.
"""

from app.services.affective_explain import (
    build_rationale,
    dominant_class,
    highlight_segments,
    week_over_week_change,
)


def test_dominant_class_selection():
    scores = {
        "exam_anxiety": 0.45,
        "conceptual_confusion": 0.78,
        "academic_helplessness": 0.12,
        "course_frustration": 0.33,
        "motivation_erosion": 0.50,
    }
    cls_name, score = dominant_class(scores)
    assert cls_name == "conceptual_confusion"
    assert score == 0.78


def test_dominant_class_empty():
    assert dominant_class({}) == ("none", 0.0)


def test_week_over_week_change():
    prev = {"exam_anxiety": 0.50, "conceptual_confusion": 0.60}
    cur = {"exam_anxiety": 0.75, "conceptual_confusion": 0.55}
    deltas = week_over_week_change(prev, cur)
    assert deltas["exam_anxiety"] == 0.25
    assert deltas["conceptual_confusion"] == -0.05


def test_build_rationale_template():
    cur = {
        "emotion_scores": {"exam_anxiety": 0.72},
        "stress_label": "high",
        "confidence": 0.88,
        "top_drivers": [
            {"token_or_marker": "not sure", "weight": 0.45},
            {"token_or_marker": "fail", "weight": 0.35},
        ],
    }
    prev = {
        "emotion_scores": {"exam_anxiety": 0.57},
    }
    rationale = build_rationale(cur, prev)
    assert "Exam Anxiety" in rationale
    assert "0.72" in rationale
    assert "up 0.15 from last week" in rationale
    assert "'not sure'" in rationale
    assert "'fail'" in rationale


def test_highlight_segments_non_overlapping():
    text = "I feel not sure about algebra and I will fail the exam."
    drivers = [
        {"token_or_marker": "not sure", "weight": 0.45},
        {"token_or_marker": "fail", "weight": 0.35},
    ]
    segments = highlight_segments(text, drivers)
    # Check that highlighted segments match
    highlighted = [s for s in segments if s["weight"] is not None]
    assert len(highlighted) == 2
    assert highlighted[0]["text"] == "not sure"
    assert highlighted[0]["weight"] == 0.45
    assert highlighted[1]["text"] == "fail"
    assert highlighted[1]["weight"] == 0.35

    # Check text reconstruction
    reconstructed = "".join(s["text"] for s in segments)
    assert reconstructed == text
