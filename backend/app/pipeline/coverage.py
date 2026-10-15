"""
backend/app/pipeline/coverage.py

Set-based eligible student calculation and received component output tracking
for Feature 22: Weekly scheduler / pipeline orchestrator.
Calculates coverage ratios for C1, C2, C3, and C4 without per-student N+1 queries
or PII leakage.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db import collections as col
from app.routers.export import get_eligible_consenting_pids
from app.schemas.contract.common import RiskTier

# Severity order for risk tiers
TIER_ORDER: Dict[str, int] = {
    RiskTier.LOW.value: 1,
    RiskTier.MEDIUM.value: 2,
    RiskTier.HIGH.value: 3,
    RiskTier.CRITICAL.value: 4,
}


@dataclass(frozen=True)
class StageCoverage:
    """Represents the student coverage state for a pipeline stage."""
    stage: str
    eligible: int
    received: int
    coverage: float
    note: Optional[str] = None


async def get_enrolled_pids(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
) -> Set[str]:
    """
    Returns the set of student PIDs actively enrolled in the course during week_index.
    Uses set-based queries against col.ENROLMENTS and checks bounds from col.COURSE_WEEKS.
    """
    cw = await db[col.COURSE_WEEKS].find_one(
        {"course_id": course_id, "week_index": week_index},
        {"start_date": 1, "end_date": 1, "_id": 0},
    )
    week_start = cw.get("start_date") if cw else None
    week_end = cw.get("end_date") if cw else None

    # Query active/enrolled students or those who unregistered after this week
    query: Dict[str, Any] = {
        "course_id": course_id,
        "$or": [
            {"status": {"$in": ["active", "enrolled", "Active", "Enrolled"]}},
            {"status": {"$in": ["withdrawn", "Withdrawn"]}, "unregistration_week": {"$gt": week_index}},
        ],
    }

    cursor = db[col.ENROLMENTS].find(
        query,
        {"pid": 1, "enrolment_start": 1, "enrolment_end": 1, "_id": 0},
    )

    enrolled: Set[str] = set()
    async for doc in cursor:
        pid = doc.get("pid")
        if not pid:
            continue
        start = doc.get("enrolment_start")
        if week_end and start and start > week_end:
            continue
        end = doc.get("enrolment_end")
        if week_start and end and end < week_start:
            continue
        enrolled.add(pid)

    return enrolled


async def get_eligible_course_pids(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
) -> Set[str]:
    """
    Computes eligible student PIDs for a course and week:
    Intersection of enrolled students and active consenting / OULAD students.
    """
    enrolled = await get_enrolled_pids(db, course_id, week_index)
    if not enrolled:
        return set()

    consenting = await get_eligible_consenting_pids(db)
    return enrolled.intersection(consenting)


async def compute_stage_coverage(
    db: AsyncIOMotorDatabase,
    stage: str,
    course_id: str,
    week_index: int,
    eligible_pids: Optional[Set[str]] = None,
) -> StageCoverage:
    """
    Computes coverage metrics (eligible count, received count, ratio) for a stage.
    Never logs or leaks student PIDs.
    """
    if eligible_pids is None:
        eligible_pids = await get_eligible_course_pids(db, course_id, week_index)

    eligible_count = len(eligible_pids)

    # If course has 0 eligible consenting students
    if eligible_count == 0:
        return StageCoverage(
            stage=stage,
            eligible=0,
            received=0,
            coverage=1.0,
            note="no eligible students",
        )

    eligible_list = list(eligible_pids)

    if stage == "lms_aggregation":
        received_pids = await db[col.BEHAVIOR_WEEKLY].distinct(
            "pid",
            {"course_id": course_id, "week_index": week_index, "pid": {"$in": eligible_list}},
        )
        received_count = len(received_pids)
        coverage = min(1.0, round(received_count / eligible_count, 4))
        return StageCoverage(stage=stage, eligible=eligible_count, received=received_count, coverage=coverage)

    elif stage == "c1":
        received_pids = await db[col.AFFECTIVE_WEEKLY].distinct(
            "pid",
            {"course_id": course_id, "week_index": week_index, "pid": {"$in": eligible_list}},
        )
        received_count = len(received_pids)
        coverage = min(1.0, round(received_count / eligible_count, 4))
        return StageCoverage(stage=stage, eligible=eligible_count, received=received_count, coverage=coverage)

    elif stage == "c2":
        received_pids = await db[col.ENGAGEMENT_TRAJECTORIES].distinct(
            "pid",
            {"course_id": course_id, "week_index": week_index, "pid": {"$in": eligible_list}},
        )
        received_count = len(received_pids)
        coverage = min(1.0, round(received_count / eligible_count, 4))
        return StageCoverage(stage=stage, eligible=eligible_count, received=received_count, coverage=coverage)

    elif stage == "c3":
        received_pids = await db[col.RISK_ASSESSMENTS].distinct(
            "pid",
            {"course_id": course_id, "week_index": week_index, "pid": {"$in": eligible_list}},
        )
        received_count = len(received_pids)
        coverage = min(1.0, round(received_count / eligible_count, 4))
        return StageCoverage(stage=stage, eligible=eligible_count, received=received_count, coverage=coverage)

    elif stage == "c4":
        # C4 eligible students are those with risk_tier >= PIPELINE_C4_MIN_TIER in C3 risk_assessments
        min_tier_name = (settings.PIPELINE_C4_MIN_TIER or "medium").lower()
        min_rank = TIER_ORDER.get(min_tier_name, 2)
        qualifying_tiers = [t for t, rank in TIER_ORDER.items() if rank >= min_rank]

        c4_eligible_pids = await db[col.RISK_ASSESSMENTS].distinct(
            "pid",
            {
                "course_id": course_id,
                "week_index": week_index,
                "pid": {"$in": eligible_list},
                "risk_tier": {"$in": qualifying_tiers},
            },
        )
        c4_eligible_count = len(c4_eligible_pids)

        if c4_eligible_count == 0:
            return StageCoverage(
                stage=stage,
                eligible=0,
                received=0,
                coverage=1.0,
                note="no eligible students",
            )

        # col.RECOMMENDATIONS stores (pid, week_index)
        received_recs = await db[col.RECOMMENDATIONS].distinct(
            "pid",
            {"week_index": week_index, "pid": {"$in": c4_eligible_pids}},
        )
        c4_received_count = len(received_recs)
        coverage = min(1.0, round(c4_received_count / c4_eligible_count, 4))
        return StageCoverage(
            stage=stage,
            eligible=c4_eligible_count,
            received=c4_received_count,
            coverage=coverage,
        )

    else:
        return StageCoverage(stage=stage, eligible=eligible_count, received=0, coverage=0.0)
