"""
backend/app/services/intervention_catalog.py

Feature 32: Canonical Intervention Catalog (Component 4 Adaptive Recommendations).
Single source of truth reused across F32, F33, F34, F35, F36, F37, F38, and F39.

Maps categorical intervention types to:
  - Staff-facing professional label
  - Student-facing neutral, empowering label (strictly NO mention of risk, distress, or failure)
  - Concise clinical/pedagogical description
  - LMS delivery module: 'counselling_booking' | 'resource_share' | 'peer_mentoring' | 'none'
"""

from typing import Any, Dict, List, Optional

# Valid delivery modules specified in research architecture
DELIVERY_MODULES = {
    "counselling_booking",
    "resource_share",
    "peer_mentoring",
    "none",
}

INTERVENTION_CATALOG: Dict[str, Dict[str, str]] = {
    "academic_support": {
        "label": "Academic Support & Tutoring",
        "student_label": "Academic Coaching & Study Support",
        "description": "One-on-one or small-group tutoring focused on conceptual mastery, coursework questions, and exam preparation.",
        "delivery_module": "resource_share",
    },
    "counselling_mental_health": {
        "label": "Mental Health & Wellbeing Counselling",
        "student_label": "Student Wellbeing & Confidential Consultation",
        "description": "Confidential advisory session with university counselling staff for stress, anxiety, or personal wellbeing.",
        "delivery_module": "counselling_booking",
    },
    "time_management_guidance": {
        "label": "Time Management & Study Skills Coaching",
        "student_label": "Personalized Study Planning & Time Management",
        "description": "Structured coaching on workload scheduling, deadline pacing, study routines, and avoiding procrastination.",
        "delivery_module": "resource_share",
    },
    "peer_mentoring": {
        "label": "Peer Mentoring & Collaborative Study",
        "student_label": "Peer Mentorship Connection",
        "description": "Pairing with a trained senior peer mentor for academic navigation, course encouragement, and study tips.",
        "delivery_module": "peer_mentoring",
    },
    "additional_learning_resources": {
        "label": "Supplementary Learning Resources",
        "student_label": "Recommended Learning Guides & Practice Materials",
        "description": "Curated digital learning modules, formative quiz walkthroughs, and foundational revision materials.",
        "delivery_module": "resource_share",
    },
    "referral_services": {
        "label": "Specialized Student Services Referral",
        "student_label": "Campus Support Services Referral",
        "description": "Referral to specialized campus student services including accessibility, financial advisory, and language support.",
        "delivery_module": "none",
    },
    # Common inbound aliases from test harnesses and C4 prototypes
    "peer_tutoring": {
        "label": "Peer Tutoring & Study Group",
        "student_label": "Peer Tutoring & Collaborative Learning",
        "description": "Structured peer tutoring session targeting specific problem-solving and assignment techniques.",
        "delivery_module": "peer_mentoring",
    },
    "academic_advising": {
        "label": "Academic Advising Consultation",
        "student_label": "Academic Advisor Consultation",
        "description": "Consultation with a designated academic advisor to review module progression and degree milestones.",
        "delivery_module": "resource_share",
    },
    "counsellor_outreach": {
        "label": "Proactive Counsellor Outreach",
        "student_label": "Student Support Check-in",
        "description": "Proactive outreach by student support professionals for confidential guidance and pastoral support.",
        "delivery_module": "counselling_booking",
    },
}

_DEFAULT_ENTRY: Dict[str, str] = {
    "label": "General Academic Support",
    "student_label": "Academic Guidance & Support",
    "description": "Tailored academic support and guidance intervention.",
    "delivery_module": "none",
}


def is_known(intervention_type: Optional[str]) -> bool:
    """Returns True if the intervention type exists in the canonical catalog."""
    if not intervention_type:
        return False
    return str(intervention_type).strip().lower() in INTERVENTION_CATALOG


def get_entry(intervention_type: Optional[str]) -> Dict[str, str]:
    """Retrieves full catalog entry with safe fallback for unknown types."""
    if not intervention_type:
        return dict(_DEFAULT_ENTRY)
    key = str(intervention_type).strip().lower()
    if key in INTERVENTION_CATALOG:
        return INTERVENTION_CATALOG[key]
    # Fallback for unknown type
    formatted_label = key.replace("_", " ").title()
    return {
        "label": f"Intervention: {formatted_label}",
        "student_label": "Academic Guidance & Support",
        "description": f"Tailored support strategy ({formatted_label}).",
        "delivery_module": "none",
    }


def get_label(intervention_type: Optional[str]) -> str:
    """Returns staff-facing descriptive label for the intervention type."""
    return get_entry(intervention_type)["label"]


def get_student_label(intervention_type: Optional[str]) -> str:
    """
    Returns student-facing friendly label.
    Invariant: Must NEVER mention risk, dropout, distress, or clinical terminology.
    """
    return get_entry(intervention_type)["student_label"]


def delivery_module_for(intervention_type: Optional[str]) -> str:
    """Returns the associated LMS delivery module identifier."""
    return get_entry(intervention_type)["delivery_module"]


def all_types() -> List[str]:
    """Returns the list of all registered intervention type keys."""
    return list(INTERVENTION_CATALOG.keys())
