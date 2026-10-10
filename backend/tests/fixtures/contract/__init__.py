"""
backend/tests/fixtures/contract/__init__.py

Feature 24 Test Fixtures:
Provides reusable valid Envelope examples and categorized invalid examples
for each v1 contract schema. Reusable by all subsystem developers.
"""

from typing import Any, Dict, List, Tuple

# ── Reusable Valid Envelopes ──────────────────────────────────────────────────

VALID_TEXT_MESSAGE_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "lms",
    "request_id": "req-msg-001",
    "data": {
        "message_id": "msg-001",
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 2,
        "source_type": "forum",
        "clean_text": "I am having serious difficulty understanding recursion and memoization.",
        "timestamp": "2026-10-10T11:50:00Z",
        "response_latency_seconds": 120.5,
        "message_length_chars": 72,
        "message_length_words": 9,
        "reply_to_id": None,
    },
}

VALID_BEHAVIOR_WEEKLY_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "lms",
    "request_id": "req-beh-001",
    "data": {
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 3,
        "login_count": 8,
        "session_minutes": 245.5,
        "clicks": 312,
        "video_play_count": 12,
        "video_pause_count": 8,
        "video_rewind_count": 5,
        "video_skip_count": 1,
        "video_completion_pct": 85.0,
        "submissions_count": 2,
        "avg_submission_delay_hours": -4.2,
    },
}

VALID_ACADEMIC_RECORD_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "lms",
    "request_id": "req-acad-001",
    "data": {
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 3,
        "ca_marks": 78.5,
        "midterm_mark": 82.0,
        "quiz_scores": [85.0, 90.0, 75.5],
        "attendance_pct": 92.5,
        "submission_delay_hours": 1.2,
    },
}

VALID_AFFECTIVE_VECTOR_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "c1",
    "request_id": "req-aff-001",
    "data": {
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 2,
        "emotion_scores": {
            "exam_anxiety": 0.45,
            "conceptual_confusion": 0.70,
            "academic_helplessness": 0.15,
            "course_frustration": 0.30,
            "motivation_erosion": 0.20,
        },
        "stress_label": "conceptual_confusion",
        "confidence": 0.88,
        "message_count": 6,
        "top_drivers": [
            {"token_or_marker": "recursion confusion", "weight": 0.75}
        ],
    },
}

VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "c2",
    "request_id": "req-eng-001",
    "data": {
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 3,
        "trajectory_label": "declining",
        "confidence": 0.81,
        "contributing_indicators": ["reduced_logins", "low_video_completion"],
    },
}

VALID_RISK_ASSESSMENT_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "c3",
    "request_id": "req-risk-001",
    "data": {
        "pid": "STU_cdbe990a",
        "course_id": "CS101",
        "week_index": 4,
        "risk_score": 0.72,
        "risk_tier": "high",
        "modality_contributions": {
            "affective": 0.40,
            "behavioral": 0.35,
            "academic": 0.25,
        },
        "top_drivers": ["high_confusion", "reduced_logins", "low_quiz_average"],
    },
}

VALID_INTERVENTION_REC_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "c4",
    "request_id": "req-rec-001",
    "data": {
        "recommendation_id": "rec-001",
        "pid": "STU_cdbe990a",
        "week_index": 4,
        "candidates": [
            {
                "intervention_type": "peer_tutoring",
                "suitability_score": 0.92,
                "rationale": "Elevated conceptual confusion in recursion suggests peer review.",
                "rank": 1,
            },
            {
                "intervention_type": "advising_outreach",
                "suitability_score": 0.76,
                "rationale": "Declining engagement trajectory calls for advisor check-in.",
                "rank": 2,
            },
        ],
        "status": "proposed",
    },
}

VALID_INTERVENTION_OUTCOME_ENVELOPE: Dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "2026-10-10T12:00:00Z",
    "source": "lms",
    "request_id": "req-out-001",
    "data": {
        "recommendation_id": "rec-001",
        "decision": "approved",
        "completed": True,
        "observed_change": "Student successfully attended peer tutoring and clarified doubts.",
        "notes_present": True,
    },
}

# Map model name to its valid full envelope fixture
ALL_VALID_FIXTURES: Dict[str, Dict[str, Any]] = {
    "TextMessageRecord": VALID_TEXT_MESSAGE_ENVELOPE,
    "BehaviorWeeklyRecord": VALID_BEHAVIOR_WEEKLY_ENVELOPE,
    "AcademicRecord": VALID_ACADEMIC_RECORD_ENVELOPE,
    "AffectiveWeeklyVector": VALID_AFFECTIVE_VECTOR_ENVELOPE,
    "EngagementTrajectory": VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE,
    "RiskAssessment": VALID_RISK_ASSESSMENT_ENVELOPE,
    "InterventionRecommendation": VALID_INTERVENTION_REC_ENVELOPE,
    "InterventionOutcome": VALID_INTERVENTION_OUTCOME_ENVELOPE,
}

# ── Invalid Envelopes Collection ──────────────────────────────────────────────
# List of (description, invalid_envelope_dict, expected_error_substring)

INVALID_FIXTURES: Dict[str, List[Tuple[str, Dict[str, Any], str]]] = {
    "TextMessageRecord": [
        (
            "Naive datetime in timestamp",
            {
                **VALID_TEXT_MESSAGE_ENVELOPE,
                "data": {
                    **VALID_TEXT_MESSAGE_ENVELOPE["data"],
                    "timestamp": "2026-10-10T11:50:00",  # No timezone offset
                },
            },
            "timestamp",
        ),
        (
            "Clean text contains identifying email",
            {
                **VALID_TEXT_MESSAGE_ENVELOPE,
                "data": {
                    **VALID_TEXT_MESSAGE_ENVELOPE["data"],
                    "clean_text": "Please reach me at student@university.edu for notes.",
                },
            },
            "clean_text",
        ),
        (
            "Clean text contains registration ID pattern IT########",
            {
                **VALID_TEXT_MESSAGE_ENVELOPE,
                "data": {
                    **VALID_TEXT_MESSAGE_ENVELOPE["data"],
                    "clean_text": "My lab partner is IT20184422.",
                },
            },
            "clean_text",
        ),
        (
            "Forbidden field name student_id",
            {
                **VALID_TEXT_MESSAGE_ENVELOPE,
                "data": {
                    **VALID_TEXT_MESSAGE_ENVELOPE["data"],
                    "student_id": "IT12345678",
                },
            },
            "student_id",
        ),
    ],
    "BehaviorWeeklyRecord": [
        (
            "Negative login count",
            {
                **VALID_BEHAVIOR_WEEKLY_ENVELOPE,
                "data": {
                    **VALID_BEHAVIOR_WEEKLY_ENVELOPE["data"],
                    "login_count": -5,
                },
            },
            "login_count",
        ),
        (
            "Video completion percentage over 100",
            {
                **VALID_BEHAVIOR_WEEKLY_ENVELOPE,
                "data": {
                    **VALID_BEHAVIOR_WEEKLY_ENVELOPE["data"],
                    "video_completion_pct": 115.0,
                },
            },
            "video_completion_pct",
        ),
    ],
    "AcademicRecord": [
        (
            "Attendance percentage over 100",
            {
                **VALID_ACADEMIC_RECORD_ENVELOPE,
                "data": {
                    **VALID_ACADEMIC_RECORD_ENVELOPE["data"],
                    "attendance_pct": 105.0,
                },
            },
            "attendance_pct",
        ),
        (
            "Invalid PID format",
            {
                **VALID_ACADEMIC_RECORD_ENVELOPE,
                "data": {
                    **VALID_ACADEMIC_RECORD_ENVELOPE["data"],
                    "pid": "STU_invalid_too_long",
                },
            },
            "pid",
        ),
    ],
    "AffectiveWeeklyVector": [
        (
            "Missing DistressClass emotion scores",
            {
                **VALID_AFFECTIVE_VECTOR_ENVELOPE,
                "data": {
                    **VALID_AFFECTIVE_VECTOR_ENVELOPE["data"],
                    "emotion_scores": {
                        "exam_anxiety": 0.45,
                        "conceptual_confusion": 0.70,
                    },
                },
            },
            "emotion_scores",
        ),
        (
            "Confidence score out of 0-1 range",
            {
                **VALID_AFFECTIVE_VECTOR_ENVELOPE,
                "data": {
                    **VALID_AFFECTIVE_VECTOR_ENVELOPE["data"],
                    "confidence": 1.45,
                },
            },
            "confidence",
        ),
    ],
    "EngagementTrajectory": [
        (
            "Unknown trajectory label enum",
            {
                **VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE,
                "data": {
                    **VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE["data"],
                    "trajectory_label": "spiraling_down",
                },
            },
            "trajectory_label",
        ),
        (
            "Contributing indicators exceeds maximum 10 items",
            {
                **VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE,
                "data": {
                    **VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE["data"],
                    "contributing_indicators": [f"indicator_{i}" for i in range(12)],
                },
            },
            "contributing_indicators",
        ),
    ],
    "RiskAssessment": [
        (
            "Modality contributions do not sum to 1.0",
            {
                **VALID_RISK_ASSESSMENT_ENVELOPE,
                "data": {
                    **VALID_RISK_ASSESSMENT_ENVELOPE["data"],
                    "modality_contributions": {
                        "affective": 0.60,
                        "behavioral": 0.50,
                        "academic": 0.40,
                    },
                },
            },
            "modality_contributions",
        ),
        (
            "Risk score negative",
            {
                **VALID_RISK_ASSESSMENT_ENVELOPE,
                "data": {
                    **VALID_RISK_ASSESSMENT_ENVELOPE["data"],
                    "risk_score": -0.15,
                },
            },
            "risk_score",
        ),
    ],
    "InterventionRecommendation": [
        (
            "Non-consecutive candidate ranks (e.g. 1 and 3)",
            {
                **VALID_INTERVENTION_REC_ENVELOPE,
                "data": {
                    **VALID_INTERVENTION_REC_ENVELOPE["data"],
                    "candidates": [
                        {
                            "intervention_type": "peer_tutoring",
                            "suitability_score": 0.90,
                            "rationale": "High confusion warrants peer tutoring.",
                            "rank": 1,
                        },
                        {
                            "intervention_type": "advising_outreach",
                            "suitability_score": 0.70,
                            "rationale": "Disengagement calls for outreach.",
                            "rank": 3,  # Missing rank 2!
                        },
                    ],
                },
            },
            "candidates",
        ),
        (
            "Empty candidates list",
            {
                **VALID_INTERVENTION_REC_ENVELOPE,
                "data": {
                    **VALID_INTERVENTION_REC_ENVELOPE["data"],
                    "candidates": [],
                },
            },
            "candidates",
        ),
    ],
    "InterventionOutcome": [
        (
            "Unknown decision enum",
            {
                **VALID_INTERVENTION_OUTCOME_ENVELOPE,
                "data": {
                    **VALID_INTERVENTION_OUTCOME_ENVELOPE["data"],
                    "decision": "deferred_decision",
                },
            },
            "decision",
        ),
        (
            "Forbidden raw notes text field included",
            {
                **VALID_INTERVENTION_OUTCOME_ENVELOPE,
                "data": {
                    **VALID_INTERVENTION_OUTCOME_ENVELOPE["data"],
                    "raw_text": "Sensitive counselling note details",
                },
            },
            "raw_text",
        ),
    ],
}
