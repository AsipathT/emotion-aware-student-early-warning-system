"""
backend/app/schemas/contract/__init__.py

Feature 24: Shared JSON schema and versioning data contracts.
Defines machine-readable data contracts connecting the LMS core and ML components:
- C1: Affective state detection
- C2: Behavioral engagement trajectory
- C3: Multimodal risk prediction
- C4: Adaptive intervention recommendation
"""

from app.schemas.contract.common import (
    ComponentSource,
    ContractBaseModel,
    CourseId,
    Decision,
    DistressClass,
    Envelope,
    Pid,
    RiskTier,
    Score01,
    SourceType,
    TrajectoryLabel,
    UtcDatetime,
    WeekIndex,
)

__all__ = [
    "ComponentSource",
    "ContractBaseModel",
    "CourseId",
    "Decision",
    "DistressClass",
    "Envelope",
    "Pid",
    "RiskTier",
    "Score01",
    "SourceType",
    "TrajectoryLabel",
    "UtcDatetime",
    "WeekIndex",
]
