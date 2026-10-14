"""Allowed input values and short descriptions shown in the UI."""

CONDITIONS = {
    "Exam Anxiety": "Worry and stress about tests that gets in the way of performance.",
    "Conceptual Confusion": "Difficulty understanding core subject concepts.",
    "Academic Helplessness": "Belief that effort will not change results, leading to giving up.",
    "Course Pacing Frustration": "Struggling to keep up with the speed or workload of the course.",
    "Motivation Erosion": "Gradual loss of interest and drive to study.",
}

TRAJECTORIES = {
    "Improving": "Engagement is getting better over recent weeks.",
    "Stable": "Engagement is steady.",
    "Declining": "Engagement is dropping over recent weeks.",
    "Volatile": "Engagement swings up and down.",
}

# Risk tier from the dropout risk score, as in the training data (upper bound inclusive).
RISK_TIER_BOUNDS = [(0.25, "Low"), (0.50, "Medium"), (0.75, "High"), (1.00, "Critical")]
RISK_TIERS = [tier for _, tier in RISK_TIER_BOUNDS]

# Order matters: ties go to the first dimension, matching how the model was trained.
C3_DIMENSIONS = ["Affective", "Behavioural", "Academic"]

INTERVENTIONS = {
    "Academic Support": "Targeted help with subject content, such as extra classes or tutoring.",
    "Additional Learning Resources": "Extra materials for self-paced study, such as notes, videos and practice sets.",
    "Attendance Support": "Monitoring attendance and working with the student and family to remove barriers.",
    "Career Guidance": "Linking study to future goals to rebuild purpose and direction.",
    "Counselling": "One-to-one sessions with a counsellor to work through stress and emotions.",
    "Engagement Support": "Activities and check-ins that rebuild participation in class.",
    "Financial Support": "Help accessing bursaries, materials or other financial assistance.",
    "Peer Mentoring": "Pairing the student with a trained peer for regular support.",
    "Referral to Relevant Services": "Referral to specialist services for urgent or complex needs.",
    "Time Management Support": "Coaching on planning, prioritising and keeping up with workload.",
}


def risk_tier(probability: float) -> str:
    for upper, tier in RISK_TIER_BOUNDS:
        if probability <= upper:
            return tier
    return RISK_TIER_BOUNDS[-1][1]


def dominant_c3(c3: dict) -> str:
    """{'affective': 0.5, 'behavioural': 0.3, 'academic': 0.2} -> 'Affective'"""
    return max(C3_DIMENSIONS, key=lambda name: c3[name.lower()])
