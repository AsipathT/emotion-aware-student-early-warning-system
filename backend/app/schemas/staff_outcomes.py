"""
backend/app/schemas/staff_outcomes.py

Feature 35: Schemas for Staff Intervention Outcome Recording (Component 4 FR8/FR9).
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class OutcomeDeltaItem(BaseModel):
    """Calculated outcome delta metrics."""
    risk_score_delta: Optional[float] = None
    tier_change: str
    trajectory_change: str
    dominant_distress_delta: Optional[float] = None
    direction: Literal["improved", "no_change", "worsened", "unknown"]


class OutcomeSuggestionResponse(BaseModel):
    """Auto-computed objective outcome suggestion for staff."""
    intervention_id: str
    current_status: str
    can_record: bool
    baseline: Dict[str, Any]
    latest: Dict[str, Any]
    delta: OutcomeDeltaItem
    weeks_to_improvement: Optional[int] = None
    suggested_direction: Literal["improved", "no_change", "worsened", "unknown"]
    is_recorded: bool
    outcome: Optional[Dict[str, Any]] = None


class OutcomeRecordRequest(BaseModel):
    """Request payload for recording final intervention outcome."""
    result: Literal["completed", "not_completed"]
    staff_category: Literal["improved", "no_change", "worsened", "unknown"]
    summary: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Public summary of observational changes (<= 300 chars, scrubbed)",
    )
    staff_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Private counselor clinical notes (LMS only, excluded from exports)",
    )


class OutcomeRecordResponse(BaseModel):
    """Response returned upon recording outcome."""
    intervention_id: str
    result: str
    category: str
    status: str
    observed_change: Optional[str] = None
    weeks_to_improvement: Optional[int] = None
    recorded_at: datetime
    message: str
