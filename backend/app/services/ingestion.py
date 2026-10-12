"""
backend/app/services/ingestion.py

Feature 23: Ingestion Service for ML Component Outputs (C1, C2, C3, C4).
Handles validation, storage document construction, idempotent upserts,
ingestion run tracking in col.INGESTION_RUNS, and operational synchronization.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.contract_version import CONTRACT_VERSION
from app.core.privacy import is_valid_pid
from app.db import collections as col
from app.schemas.contract.common import Envelope
from app.schemas.contract.v1.c1_affective import AffectiveWeeklyVector
from app.schemas.contract.v1.c2_behavioral import EngagementTrajectory
from app.schemas.contract.v1.c3_risk import RiskAssessment
from app.schemas.contract.v1.c4_intervention import (
    InterventionOutcome,
    InterventionRecommendation,
)


async def create_ingestion_run(
    db: AsyncIOMotorDatabase,
    component: str,
    run_id: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    """Initialize a tracked ingestion run in col.INGESTION_RUNS."""
    actual_run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "run_id": actual_run_id,
        "component": component,
        "started_at": now,
        "ended_at": None,
        "status": "running",
        "records_processed": 0,
        "error_message": None,
        "details": None,
        "dry_run": dry_run,
        "ingested_at": now,
        "source_version": CONTRACT_VERSION,
    }
    await db[col.INGESTION_RUNS].insert_one(doc)
    return actual_run_id


async def complete_ingestion_run(
    db: AsyncIOMotorDatabase,
    run_id: str,
    status_str: str,
    records_processed: int,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Finalize an ingestion run with status and timing."""
    now = datetime.now(timezone.utc)
    await db[col.INGESTION_RUNS].update_one(
        {"run_id": run_id},
        {
            "$set": {
                "ended_at": now,
                "status": status_str,
                "records_processed": records_processed,
                "error_message": error_message,
                "details": details or {},
            }
        },
    )


def _normalize_payload(
    payload_data: Union[Any, List[Any]]
) -> List[Any]:
    """Ensures input data is a list of records."""
    if isinstance(payload_data, list):
        return payload_data
    return [payload_data]


# ── Feature 23: C1 Affective State Detection Ingestion ────────────────────────

async def ingest_affective_vectors(
    db: AsyncIOMotorDatabase,
    envelope: Envelope[Union[AffectiveWeeklyVector, List[AffectiveWeeklyVector]]],
    run_id: str,
) -> int:
    """
    Ingests AffectiveWeeklyVector items into col.AFFECTIVE_WEEKLY.
    Enforces PID validity and compound uniqueness on (pid, course_id, week_index).
    """
    records = _normalize_payload(envelope.data)
    now = datetime.now(timezone.utc)
    processed_count = 0

    for rec in records:
        if not is_valid_pid(rec.pid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid student PID '{rec.pid}'. Must adhere to format STU_xxxxxxxx.",
            )

        doc = {
            "pid": rec.pid,
            "course_id": rec.course_id,
            "week_index": rec.week_index,
            "emotion_scores": {
                (k.value if hasattr(k, "value") else str(k)): float(v)
                for k, v in rec.emotion_scores.items()
            },
            "stress_label": rec.stress_label,
            "confidence": float(rec.confidence),
            "message_count": rec.message_count,
            "top_drivers": [d.model_dump() for d in rec.top_drivers],
            "schema_version": 1,
            "source_version": envelope.schema_version,
            "source": envelope.source,
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Idempotent upsert matching compound unique index idx_affective_weekly_compound_unique
        await db[col.AFFECTIVE_WEEKLY].update_one(
            {
                "pid": rec.pid,
                "course_id": rec.course_id,
                "week_index": rec.week_index,
            },
            {
                "$set": doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )
        processed_count += 1

    return processed_count


# ── Feature 23: C2 Behavioral Trajectory Ingestion ────────────────────────────

async def ingest_engagement_trajectories(
    db: AsyncIOMotorDatabase,
    envelope: Envelope[Union[EngagementTrajectory, List[EngagementTrajectory]]],
    run_id: str,
) -> int:
    """
    Ingests EngagementTrajectory items into col.ENGAGEMENT_TRAJECTORIES.
    Enforces PID validity and compound uniqueness on (pid, course_id, week_index).
    """
    records = _normalize_payload(envelope.data)
    now = datetime.now(timezone.utc)
    processed_count = 0

    for rec in records:
        if not is_valid_pid(rec.pid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid student PID '{rec.pid}'. Must adhere to format STU_xxxxxxxx.",
            )

        traj_val = (
            rec.trajectory_label.value
            if hasattr(rec.trajectory_label, "value")
            else str(rec.trajectory_label)
        )
        doc = {
            "pid": rec.pid,
            "course_id": rec.course_id,
            "week_index": rec.week_index,
            "trajectory_label": traj_val,
            "confidence": float(rec.confidence),
            "contributing_indicators": list(rec.contributing_indicators),
            "schema_version": 1,
            "source_version": envelope.schema_version,
            "source": envelope.source,
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Idempotent upsert matching compound unique index
        await db[col.ENGAGEMENT_TRAJECTORIES].update_one(
            {
                "pid": rec.pid,
                "course_id": rec.course_id,
                "week_index": rec.week_index,
            },
            {
                "$set": doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )
        processed_count += 1

    return processed_count


# ── Feature 23: C3 Multimodal Risk Assessment Ingestion ───────────────────────

async def ingest_risk_assessments(
    db: AsyncIOMotorDatabase,
    envelope: Envelope[Union[RiskAssessment, List[RiskAssessment]]],
    run_id: str,
) -> int:
    """
    Ingests RiskAssessment items into col.RISK_ASSESSMENTS.
    Enforces PID validity and compound uniqueness on (pid, course_id, week_index).
    """
    records = _normalize_payload(envelope.data)
    now = datetime.now(timezone.utc)
    processed_count = 0

    for rec in records:
        if not is_valid_pid(rec.pid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid student PID '{rec.pid}'. Must adhere to format STU_xxxxxxxx.",
            )

        tier_val = (
            rec.risk_tier.value
            if hasattr(rec.risk_tier, "value")
            else str(rec.risk_tier)
        )
        doc = {
            "pid": rec.pid,
            "course_id": rec.course_id,
            "week_index": rec.week_index,
            "risk_score": float(rec.risk_score),
            "risk_tier": tier_val,
            "modality_contributions": rec.modality_contributions.model_dump(),
            "top_drivers": list(rec.top_drivers),
            "schema_version": 1,
            "source_version": envelope.schema_version,
            "source": envelope.source,
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Idempotent upsert matching compound unique index
        await db[col.RISK_ASSESSMENTS].update_one(
            {
                "pid": rec.pid,
                "course_id": rec.course_id,
                "week_index": rec.week_index,
            },
            {
                "$set": doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )
        processed_count += 1

    return processed_count


# ── Feature 23: C4 Intervention Recommendations Ingestion ────────────────────

async def ingest_recommendations(
    db: AsyncIOMotorDatabase,
    envelope: Envelope[Union[InterventionRecommendation, List[InterventionRecommendation]]],
    run_id: str,
) -> int:
    """
    Ingests InterventionRecommendation items into col.RECOMMENDATIONS and
    synchronizes operational intervention items in col.INTERVENTIONS.
    """
    records = _normalize_payload(envelope.data)
    now = datetime.now(timezone.utc)
    processed_count = 0

    for rec in records:
        if not is_valid_pid(rec.pid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid student PID '{rec.pid}'. Must adhere to format STU_xxxxxxxx.",
            )

        doc = {
            "recommendation_id": rec.recommendation_id,
            "pid": rec.pid,
            "week_index": rec.week_index,
            "candidates": [c.model_dump() for c in rec.candidates],
            "status": rec.status,
            "schema_version": 1,
            "source_version": envelope.schema_version,
            "source": envelope.source,
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Upsert recommendation
        await db[col.RECOMMENDATIONS].update_one(
            {"recommendation_id": rec.recommendation_id},
            {
                "$set": doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )

        # Operational tracking: synchronize interventions in col.INTERVENTIONS
        for cand in rec.candidates:
            int_id = f"INT_{rec.recommendation_id}_{cand.rank}"
            int_doc = {
                "intervention_id": int_id,
                "recommendation_id": rec.recommendation_id,
                "pid": rec.pid,
                "course_id": cand.action_type,  # Categorized context
                "intervention_type": cand.action_type,
                "status": rec.status or "proposed",
                "schema_version": 1,
                "source_version": envelope.schema_version,
                "source": envelope.source,
                "ingestion_run_id": run_id,
                "ingested_at": now,
                "created_at": now,
            }
            await db[col.INTERVENTIONS].update_one(
                {"intervention_id": int_id},
                {
                    "$set": int_doc,
                    "$setOnInsert": {"_id": str(uuid.uuid4())},
                },
                upsert=True,
            )

        processed_count += 1

    return processed_count


# ── Feature 23: Intervention Outcomes Ingestion (Staff / C4 Feedback Loop) ───

async def ingest_intervention_outcomes(
    db: AsyncIOMotorDatabase,
    envelope: Envelope[Union[InterventionOutcome, List[InterventionOutcome]]],
    run_id: str,
) -> int:
    """
    Ingests InterventionOutcome items into col.INTERVENTION_OUTCOMES
    and updates corresponding intervention operational status.
    """
    records = _normalize_payload(envelope.data)
    now = datetime.now(timezone.utc)
    processed_count = 0

    for rec in records:
        dec_val = (
            rec.decision.value
            if hasattr(rec.decision, "value")
            else str(rec.decision)
        )
        doc = {
            "recommendation_id": rec.recommendation_id,
            "decision": dec_val,
            "completed": rec.completed,
            "observed_change": rec.observed_change,
            "notes_present": rec.notes_present,
            "schema_version": 1,
            "source_version": envelope.schema_version,
            "source": envelope.source,
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Upsert outcome record
        await db[col.INTERVENTION_OUTCOMES].update_one(
            {"recommendation_id": rec.recommendation_id},
            {
                "$set": doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )

        # Update matching interventions status
        new_status = "completed" if rec.completed else dec_val
        await db[col.INTERVENTIONS].update_many(
            {"recommendation_id": rec.recommendation_id},
            {"$set": {"status": new_status, "updated_at": now}},
        )
        processed_count += 1

    return processed_count
