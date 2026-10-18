"""
Pydantic v2 schemas and envelope builders for Component 2 data interchange.
Mirrors the contract without importing from backend/.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IT_PATTERN_REGEX = re.compile(r"IT\d{8}")


def _validate_no_pii(text: str, field_name: str) -> None:
    """Ensures string does not contain an email or the pattern IT followed by 8 digits."""
    if EMAIL_REGEX.search(text):
        raise ValueError(f"{field_name} must not contain email addresses.")
    if IT_PATTERN_REGEX.search(text):
        raise ValueError(f"{field_name} must not contain the pattern IT followed by 8 digits.")


class BehaviorRecord(BaseModel):
    """Weekly student LMS interaction record exported from GET /api/v1/export/behavior."""

    model_config = ConfigDict(extra="forbid")

    pid: str = Field(..., pattern=r"^STU_[0-9a-fA-F]{8}$")
    course_id: str = Field(..., min_length=1, max_length=128)
    week_index: int = Field(..., ge=0)
    login_count: int = Field(..., ge=0)
    session_minutes: float = Field(..., ge=0.0)
    clicks: int = Field(..., ge=0)
    video_play_count: int = Field(..., ge=0)
    video_pause_count: int = Field(..., ge=0)
    video_rewind_count: int = Field(..., ge=0)
    video_skip_count: int = Field(..., ge=0)
    video_completion_pct: float = Field(..., ge=0.0, le=100.0)
    submissions_count: int = Field(..., ge=0)
    avg_submission_delay_hours: float


class TrajectoryRecord(BaseModel):
    """Component 2 engagement trajectory classification record for ingest."""

    model_config = ConfigDict(extra="forbid")

    pid: str = Field(..., pattern=r"^STU_[0-9a-fA-F]{8}$")
    course_id: str = Field(..., min_length=1, max_length=128)
    week_index: int = Field(..., ge=0)
    trajectory_label: Literal["stable", "improving", "declining", "volatile"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    contributing_indicators: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("course_id")
    @classmethod
    def check_course_id_pii(cls, v: str) -> str:
        _validate_no_pii(v, "course_id")
        return v

    @field_validator("contributing_indicators")
    @classmethod
    def check_indicators_pii(cls, v: List[str]) -> List[str]:
        for ind in v:
            _validate_no_pii(ind, "contributing_indicators")
        return v


def build_envelope(
    records: List[TrajectoryRecord], request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs standard trajectory ingest envelope:
    {
      "schema_version": "1.0",
      "generated_at": ISO-8601 UTC with timezone,
      "source": "c2",
      "request_id": str,
      "data": [TrajectoryRecord.model_dump()...]
    }
    """
    req_id = request_id if request_id and request_id.strip() else str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "source": "c2",
        "request_id": req_id,
        "data": [r.model_dump() for r in records],
    }
