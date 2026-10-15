"""
backend/app/schemas/contract/v1/c4_intervention.py

Contract schemas for Component 4: Adaptive Intervention Recommendation.
- InterventionRecommendation: Inbound from C4 to LMS (Feature 23). Ranked action candidates.
- InterventionOutcome: Feedback loop from LMS to C4. Staff decisions and student progress.
"""

from typing import List, Optional
from pydantic import Field, field_validator

from app.schemas.contract.common import (
    CleanText,
    ContractBaseModel,
    Decision,
    Pid,
    Score01,
    WeekIndex,
)


class InterventionCandidate(ContractBaseModel):
    """
    A single suggested intervention strategy evaluated by Component 4.
    """
    intervention_type: CleanText = Field(
        ...,
        min_length=1,
        description="Categorical type of suggested intervention (e.g. peer_tutoring, academic_advising, counsellor_outreach)",
    )
    suitability_score: Score01 = Field(
        ...,
        description="Predicted match suitability score for this student's risk profile (0.0 - 1.0)",
    )
    rationale: CleanText = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Model explanation justifying why this intervention was selected (max 500 chars)",
    )
    rank: int = Field(
        ...,
        ge=1,
        description="Ordinal recommendation priority rank (1 = highest priority)",
    )


class InterventionRecommendation(ContractBaseModel):
    """
    Ranked intervention recommendations generated for an at-risk student.
    Transmitted from Component 4 to LMS database (Feature 23).
    Candidates must contain 1-10 items with unique, consecutive ranks starting at 1.
    """
    recommendation_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this recommendation batch",
    )
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week of recommendation",
    )
    candidates: List[InterventionCandidate] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of 1 to 10 recommended intervention candidates ordered by priority",
    )
    status: CleanText = Field(
        ...,
        min_length=1,
        description="Operational status of the recommendation (e.g. proposed, active, resolved)",
    )

    @field_validator("candidates")
    @classmethod
    def validate_candidate_ranks(
        cls, candidates: List[InterventionCandidate]
    ) -> List[InterventionCandidate]:
        if not (1 <= len(candidates) <= 10):
            raise ValueError(
                f"candidates list must contain between 1 and 10 items (got {len(candidates)})."
            )

        ranks = [c.rank for c in candidates]
        expected_ranks = list(range(1, len(candidates) + 1))
        sorted_ranks = sorted(ranks)

        if sorted_ranks != expected_ranks:
            raise ValueError(
                f"Candidate ranks must be unique and consecutive starting from 1 to {len(candidates)}. "
                f"Got ranks: {ranks}."
            )
        return candidates


class InterventionOutcome(ContractBaseModel):
    """
    Operational disposition and evaluation of an intervention recommendation.
    Feeds back from LMS / academic staff back into Component 4 for model refinement.
    NOTE: Never stores raw counsellor or staff narrative note text to safeguard privacy.
    Only records the boolean indicator `notes_present`.
    """
    recommendation_id: str = Field(
        ...,
        min_length=1,
        description="Referenced intervention recommendation identifier",
    )
    decision: Decision = Field(
        ...,
        description="Staff decision on the recommendation (approved, modified, rejected)",
    )
    completed: bool = Field(
        ...,
        description="Whether the selected intervention was delivered and finalized",
    )
    observed_change: Optional[CleanText] = Field(
        default=None,
        max_length=500,
        description="Optional brief observation of academic or affective shift post-intervention (max 500 chars)",
    )
    notes_present: bool = Field(
        ...,
        description=(
            "Indicates whether staff added detailed internal counseling notes. "
            "Staff note text is strictly forbidden from entering contract data."
        ),
    )
