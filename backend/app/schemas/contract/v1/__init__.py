"""
backend/app/schemas/contract/v1/__init__.py

Exports all Version 1 data contract models and component schema definitions.
"""

from app.schemas.contract.v1.c1_affective import (
    AffectiveWeeklyVector,
    TextMessageRecord,
    TopDriver,
)
from app.schemas.contract.v1.c2_behavioral import (
    BehaviorWeeklyRecord,
    EngagementTrajectory,
)
from app.schemas.contract.v1.c3_risk import (
    AcademicRecord,
    ModalityContributions,
    RiskAssessment,
)
from app.schemas.contract.v1.c4_intervention import (
    InterventionCandidate,
    InterventionOutcome,
    InterventionRecommendation,
)

# Registry of top-level v1 models exchanged between LMS and ML components
V1_CONTRACT_MODELS = (
    TextMessageRecord,
    BehaviorWeeklyRecord,
    AcademicRecord,
    AffectiveWeeklyVector,
    EngagementTrajectory,
    RiskAssessment,
    InterventionRecommendation,
    InterventionOutcome,
)

__all__ = [
    "AcademicRecord",
    "AffectiveWeeklyVector",
    "BehaviorWeeklyRecord",
    "EngagementTrajectory",
    "InterventionCandidate",
    "InterventionOutcome",
    "InterventionRecommendation",
    "ModalityContributions",
    "RiskAssessment",
    "TextMessageRecord",
    "TopDriver",
    "V1_CONTRACT_MODELS",
]
