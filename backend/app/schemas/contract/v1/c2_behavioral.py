"""
backend/app/schemas/contract/v1/c2_behavioral.py

Contract schemas for Component 2: Behavioral Engagement Trajectory.
- BehaviorWeeklyRecord: Outbound from LMS to C2 (Feature 21). LMS clickstream & video telemetry.
- EngagementTrajectory: Inbound from C2 to LMS (Feature 23). Trend classification & trajectory.
"""

from typing import List
from pydantic import Field

from app.schemas.contract.common import (
    CleanText,
    ContractBaseModel,
    CourseId,
    Pid,
    Score01,
    TrajectoryLabel,
    WeekIndex,
)


class BehaviorWeeklyRecord(ContractBaseModel):
    """
    Weekly behavioral telemetry aggregated from LMS logs, video player events,
    and assignment submissions.
    Transmitted from LMS to Component 2 (Behavioral Engagement Trajectory).
    """
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    course_id: CourseId = Field(
        ...,
        description="Course institutional identifier",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week of observation",
    )
    login_count: int = Field(
        ...,
        ge=0,
        description="Total distinct logins/sessions started during the week",
    )
    session_minutes: float = Field(
        ...,
        ge=0.0,
        description="Total active time spent on the platform in minutes",
    )
    clicks: int = Field(
        ...,
        ge=0,
        description="Total interaction events (clicks, navigations, downloads)",
    )
    video_play_count: int = Field(
        ...,
        ge=0,
        description="Number of video play events triggered",
    )
    video_pause_count: int = Field(
        ...,
        ge=0,
        description="Number of video pause events triggered",
    )
    video_rewind_count: int = Field(
        ...,
        ge=0,
        description="Number of backward seek / rewind events (indicator of difficulty)",
    )
    video_skip_count: int = Field(
        ...,
        ge=0,
        description="Number of forward seek / skip events",
    )
    video_completion_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Average video completion percentage across assigned lectures (0.0 to 100.0)",
    )
    submissions_count: int = Field(
        ...,
        ge=0,
        description="Number of assignments or lab tasks submitted during the week",
    )
    avg_submission_delay_hours: float = Field(
        ...,
        description=(
            "Average hours relative to deadline. "
            "Negative value indicates early submission (e.g. -4.5 = 4.5 hours early); "
            "positive value indicates late submission."
        ),
    )


class EngagementTrajectory(ContractBaseModel):
    """
    Longitudinal engagement trajectory classification and confidence assessment.
    Transmitted from Component 2 to LMS database (Feature 23).
    """
    pid: Pid = Field(
        ...,
        description="Pseudonymized student identifier (Feature 5 format)",
    )
    course_id: CourseId = Field(
        ...,
        description="Course institutional identifier",
    )
    week_index: WeekIndex = Field(
        ...,
        description="Zero-indexed academic week of evaluation",
    )
    trajectory_label: TrajectoryLabel = Field(
        ...,
        description="Longitudinal trend classification (stable, improving, declining, volatile)",
    )
    confidence: Score01 = Field(
        ...,
        description="Model confidence in trajectory assignment between 0.0 and 1.0",
    )
    contributing_indicators: List[CleanText] = Field(
        default_factory=list,
        max_length=10,
        description="Top behavioral features or metrics driving the trajectory classification (max 10)",
    )
