"""
backend/app/routers/ingest.py

Feature 23: Component Data Ingestion API Endpoints.
Receives machine learning model inferences and predictions from Components 1-4:
  - POST /api/v1/ingest/affective        <- C1 (Affective State Detection)
  - POST /api/v1/ingest/behavior         <- C2 (Behavioral Engagement Trajectory)
  - POST /api/v1/ingest/risk             <- C3 (Multimodal Risk Prediction)
  - POST /api/v1/ingest/recommendations  <- C4 (Intervention Recommendation)
  - POST /api/v1/ingest/outcomes         <- C4 Feedback / Staff Intervention Delivery
  - GET  /api/v1/ingest/runs             <- Administrative Run Observability
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.component_auth import ExportActor, ingest_actor
from app.core.contract_version import CONTRACT_VERSION
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.db import collections as col
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import Envelope
from app.schemas.contract.v1.c1_affective import AffectiveWeeklyVector
from app.schemas.contract.v1.c2_behavioral import EngagementTrajectory
from app.schemas.contract.v1.c3_risk import RiskAssessment
from app.schemas.contract.v1.c4_intervention import (
    InterventionOutcome,
    InterventionRecommendation,
)
from app.services.audit import log_event
from app.services.ingestion import (
    complete_ingestion_run,
    create_ingestion_run,
    ingest_affective_vectors,
    ingest_engagement_trajectories,
    ingest_intervention_outcomes,
    ingest_recommendations,
    ingest_risk_assessments,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingestion"])


def _build_response_envelope(
    run_id: str,
    component: str,
    records_count: int,
    status_str: str = "completed",
) -> Dict[str, Any]:
    """Builds a standardized confirmation envelope."""
    return {
        "schema_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "lms",
        "request_id": str(uuid.uuid4()),
        "data": {
            "run_id": run_id,
            "component": component,
            "status": status_str,
            "records_processed": records_count,
        },
    }


# ── 1. C1 Affective State Vector Ingestion ────────────────────────────────────

@router.post(
    "/affective",
    summary="Ingest Component 1 Affective State Vectors",
    description="Idempotently upserts weekly emotional distress distributions into col.AFFECTIVE_WEEKLY.",
    status_code=status.HTTP_200_OK,
)
async def ingest_c1_affective(
    payload: Envelope[Union[AffectiveWeeklyVector, List[AffectiveWeeklyVector]]],
    request: Request,
    actor: ExportActor = Depends(ingest_actor("c1")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    run_id = await create_ingestion_run(db=db, component="c1")
    try:
        count = await ingest_affective_vectors(db=db, envelope=payload, run_id=run_id)
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=count,
            details={"source": payload.source, "schema_version": payload.schema_version},
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            target_type=col.AFFECTIVE_WEEKLY,
            target_id=run_id,
            outcome=AuditOutcome.SUCCESS,
            details={"records_processed": count, "component": "c1"},
        )
        return _build_response_envelope(run_id=run_id, component="c1", records_count=count)
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest C1 affective vectors: {exc}",
        )


# ── 2. C2 Behavioral Trajectory Ingestion ──────────────────────────────────────

@router.post(
    "/behavior",
    summary="Ingest Component 2 Behavioral Engagement Trajectories",
    description="Idempotently upserts weekly behavioral engagement trends into col.ENGAGEMENT_TRAJECTORIES.",
    status_code=status.HTTP_200_OK,
)
async def ingest_c2_behavior(
    payload: Envelope[Union[EngagementTrajectory, List[EngagementTrajectory]]],
    request: Request,
    actor: ExportActor = Depends(ingest_actor("c2")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    run_id = await create_ingestion_run(db=db, component="c2")
    try:
        count = await ingest_engagement_trajectories(db=db, envelope=payload, run_id=run_id)
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=count,
            details={"source": payload.source, "schema_version": payload.schema_version},
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            target_type=col.ENGAGEMENT_TRAJECTORIES,
            target_id=run_id,
            outcome=AuditOutcome.SUCCESS,
            details={"records_processed": count, "component": "c2"},
        )
        return _build_response_envelope(run_id=run_id, component="c2", records_count=count)
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest C2 engagement trajectories: {exc}",
        )


# ── 3. C3 Multimodal Risk Assessment Ingestion ─────────────────────────────────

@router.post(
    "/risk",
    summary="Ingest Component 3 Multimodal Risk Assessments",
    description="Idempotently upserts synthesized dropout risk assessments into col.RISK_ASSESSMENTS.",
    status_code=status.HTTP_200_OK,
)
async def ingest_c3_risk(
    payload: Envelope[Union[RiskAssessment, List[RiskAssessment]]],
    request: Request,
    actor: ExportActor = Depends(ingest_actor("c3")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    run_id = await create_ingestion_run(db=db, component="c3")
    try:
        count = await ingest_risk_assessments(db=db, envelope=payload, run_id=run_id)
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=count,
            details={"source": payload.source, "schema_version": payload.schema_version},
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            target_type=col.RISK_ASSESSMENTS,
            target_id=run_id,
            outcome=AuditOutcome.SUCCESS,
            details={"records_processed": count, "component": "c3"},
        )
        return _build_response_envelope(run_id=run_id, component="c3", records_count=count)
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest C3 risk assessments: {exc}",
        )


# ── 4. C4 Intervention Recommendations Ingestion ──────────────────────────────

@router.post(
    "/recommendations",
    summary="Ingest Component 4 Intervention Recommendations",
    description="Upserts ranked adaptive intervention recommendations into col.RECOMMENDATIONS and synchronizes col.INTERVENTIONS.",
    status_code=status.HTTP_200_OK,
)
async def ingest_c4_recommendations(
    payload: Envelope[Union[InterventionRecommendation, List[InterventionRecommendation]]],
    request: Request,
    actor: ExportActor = Depends(ingest_actor("c4")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    run_id = await create_ingestion_run(db=db, component="c4")
    try:
        count = await ingest_recommendations(db=db, envelope=payload, run_id=run_id)
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=count,
            details={"source": payload.source, "schema_version": payload.schema_version},
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            target_type=col.RECOMMENDATIONS,
            target_id=run_id,
            outcome=AuditOutcome.SUCCESS,
            details={"records_processed": count, "component": "c4"},
        )
        return _build_response_envelope(run_id=run_id, component="c4", records_count=count)
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest C4 recommendations: {exc}",
        )


# ── 5. Intervention Outcomes (Feedback Loop) ──────────────────────────────────

@router.post(
    "/outcomes",
    summary="Record Intervention Outcome / Efficacy Feedback",
    description="Records staff decisions and post-intervention evaluations into col.INTERVENTION_OUTCOMES.",
    status_code=status.HTTP_200_OK,
)
async def ingest_intervention_outcomes_endpoint(
    payload: Envelope[Union[InterventionOutcome, List[InterventionOutcome]]],
    request: Request,
    actor: ExportActor = Depends(ingest_actor("c4")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    run_id = await create_ingestion_run(db=db, component="c4_feedback")
    try:
        count = await ingest_intervention_outcomes(db=db, envelope=payload, run_id=run_id)
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=count,
            details={"source": payload.source, "schema_version": payload.schema_version},
        )
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_IMPORTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            target_type=col.INTERVENTION_OUTCOMES,
            target_id=run_id,
            outcome=AuditOutcome.SUCCESS,
            details={"records_processed": count, "component": "c4_feedback"},
        )
        return _build_response_envelope(run_id=run_id, component="c4_feedback", records_count=count)
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest intervention outcomes: {exc}",
        )


# ── 6. Ingestion Runs Query (Admin / Auditor Observability) ───────────────────

@router.get(
    "/runs",
    summary="List Recent Ingestion Batch Runs",
    description="Returns tracked ingestion pipeline executions from col.INGESTION_RUNS.",
)
async def list_ingestion_runs(
    component: Optional[str] = Query(None, description="Filter by component identifier (c1, c2, c3, c4, oulad_importer, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Max runs to return"),
    skip: int = Query(0, ge=0, description="Records to skip"),
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query_filter: Dict[str, Any] = {}
    if component:
        query_filter["component"] = component.lower().strip()

    cursor = (
        db[col.INGESTION_RUNS]
        .find(query_filter, {"_id": 0})
        .sort("started_at", -1)
        .skip(skip)
        .limit(limit)
    )
    runs = await cursor.to_list(length=limit)
    total = await db[col.INGESTION_RUNS].count_documents(query_filter)

    return {
        "schema_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "lms",
        "total": total,
        "limit": limit,
        "skip": skip,
        "runs": runs,
    }
