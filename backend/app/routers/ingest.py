"""
backend/app/routers/ingest.py

Feature 23: Ingestion Endpoints for ML Component Outputs.
Provides read/write pipeline for components C1, C2, C3, and C4:
  - POST /api/v1/ingest/affective (C1 -> col.AFFECTIVE_WEEKLY)
  - POST /api/v1/ingest/trajectory (C2 -> col.ENGAGEMENT_TRAJECTORIES)
  - POST /api/v1/ingest/risk (C3 -> col.RISK_ASSESSMENTS)
  - POST /api/v1/ingest/recommendations (C4 -> col.RECOMMENDATIONS)

Enforces:
  - Strict component authentication via X-Component-Key header (no Bearer token allowed)
  - Request body size capped at INGEST_MAX_BODY_BYTES (HTTP 413)
  - Batch size capped at INGEST_MAX_BATCH (HTTP 413)
  - Two-stage validation:
      Stage 1: All-or-nothing contract validation via validated_envelope (HTTP 422, sanitized paths)
      Stage 2: Batch business validation (UNKNOWN_PID, NOT_ENROLLED, NO_CONSENT, DUPLICATE_IN_BATCH, CONFLICT_STAFF_DECISION)
  - Deterministic document _id formatting and bulk ReplaceOne (upsert=True)
  - Ingestion run tracking (IngestionRunStorage) with statuses running, completed, partial, failed
  - Best-effort audit logging (AuditAction.DATA_INGESTED)
  - Full dry_run support
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReplaceOne

from app.core.component_auth import IngestActor, ingest_actor
from app.core.config import settings
from app.core.contract_validation import validated_envelope
from app.core.database import get_db
from app.db import collections as col
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import Envelope
from app.schemas.contract.v1.c1_affective import AffectiveWeeklyVector
from app.schemas.contract.v1.c2_behavioral import EngagementTrajectory
from app.schemas.contract.v1.c3_risk import RiskAssessment
from app.schemas.contract.v1.c4_intervention import InterventionRecommendation
from app.schemas.ingest import IngestResponse, RejectedRecordItem
from app.services.audit import log_event

logger = logging.getLogger("app.ingest")


async def check_body_size_limit(request: Request) -> None:
    """Rejects incoming ingestion requests exceeding the configured byte cap."""
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.INGEST_MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Request payload size exceeds maximum limit of {settings.INGEST_MAX_BODY_BYTES} bytes.",
        )
    raw_body = await request.body()
    if len(raw_body) > settings.INGEST_MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Request payload size ({len(raw_body)} bytes) exceeds maximum limit of {settings.INGEST_MAX_BODY_BYTES} bytes.",
        )


router = APIRouter(
    prefix="/api/v1/ingest",
    tags=["ingest"],
    dependencies=[Depends(check_body_size_limit)],
)


# ── Shared Ingestion Pipeline Engine ──────────────────────────────────────────

async def process_component_ingestion(
    request: Request,
    db: AsyncIOMotorDatabase,
    actor: IngestActor,
    envelope: Envelope[Any],
    target_collection: str,
    dry_run: bool = False,
    is_recommendations: bool = False,
    source_tag: Optional[str] = None,
) -> IngestResponse:
    """
    Executes the two-stage validation and idempotent persistence workflow for component outputs.
    """
    # 1. Envelope source must match authenticated component
    source_val = envelope.source.value.lower() if hasattr(envelope.source, "value") else str(envelope.source).lower()
    if source_val != actor.component.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Envelope source '{source_val}' does not match authenticated component '{actor.component}'.",
        )

    # 2. Normalize records and verify batch size limit
    records: List[Any] = envelope.data if isinstance(envelope.data, list) else [envelope.data]
    received_count = len(records)
    if received_count > settings.INGEST_MAX_BATCH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size {received_count} exceeds maximum allowed limit of {settings.INGEST_MAX_BATCH} records.",
        )

    # 3. Initialize Ingestion Run tracking
    run_id = f"run_{uuid.uuid4().hex}"
    started_at = datetime.now(timezone.utc)

    run_doc: Dict[str, Any] = {
        "_id": run_id,
        "run_id": run_id,
        "component": actor.component,
        "started_at": started_at,
        "ended_at": None,
        "status": "running",
        "records_processed": 0,
        "details": None,
        "dry_run": dry_run,
        "schema_version": 1,
        "ingested_at": started_at,
        "source_version": str(envelope.schema_version),
        "source": source_tag or "ingest",
    }
    await db[col.INGESTION_RUNS].insert_one(run_doc)

    try:
        # 4. Stage 2 Batch Lookups
        batch_pids: List[str] = list({r.pid for r in records})

        # Lookup 1: Identity Vault
        vault_docs = await db[col.IDENTITY_VAULT].find(
            {"pid": {"$in": batch_pids}},
            {"_id": 0, "pid": 1, "is_imported": 1, "source": 1},
        ).to_list(None)
        known_pids: Set[str] = {d["pid"] for d in vault_docs}
        oulad_pids: Set[str] = {
            d["pid"]
            for d in vault_docs
            if d.get("is_imported") is True or d.get("source") == "oulad"
        }

        # Lookup 2: Single aggregation for active consent
        active_notice = await db[col.CONSENT_NOTICES].find_one({"is_active": True})
        consenting_pids: Set[str] = set()
        if active_notice:
            pipeline = [
                {"$match": {"pid": {"$in": batch_pids}, "notice_version": active_notice["version"]}},
                {"$sort": {"timestamp": -1}},
                {"$group": {"_id": "$pid", "latest_decision": {"$first": "$decision"}}},
                {"$match": {"latest_decision": "accepted"}},
            ]
            async for consent_doc in db[col.CONSENT_RECORDS].aggregate(pipeline):
                consenting_pids.add(consent_doc["_id"])

        # Lookup 3: Enrolments (for weekly records)
        enrolled_set: Set[Tuple[str, str]] = set()
        if not is_recommendations:
            enr_docs = await db[col.ENROLMENTS].find(
                {
                    "pid": {"$in": batch_pids},
                    "status": {"$in": ["active", "completed", "withdrawn"]},
                },
                {"_id": 0, "pid": 1, "course_id": 1},
            ).to_list(None)
            enrolled_set = {(e["pid"], str(e["course_id"])) for e in enr_docs}

        # Lookup 4: Existing recommendations and outcomes (recommendations only)
        existing_rec_status_map: Dict[str, str] = {}
        decided_outcomes_set: Set[str] = set()
        if is_recommendations:
            rec_ids = list({r.recommendation_id for r in records})
            rec_docs = await db[col.RECOMMENDATIONS].find(
                {"recommendation_id": {"$in": rec_ids}},
                {"_id": 0, "recommendation_id": 1, "status": 1},
            ).to_list(None)
            existing_rec_status_map = {d["recommendation_id"]: str(d.get("status", "")).strip().lower() for d in rec_docs}

            outcome_rec_ids = await db[col.INTERVENTION_OUTCOMES].distinct(
                "recommendation_id",
                {"recommendation_id": {"$in": rec_ids}},
            )
            decided_outcomes_set = set(outcome_rec_ids)

        # 5. Evaluate Records in order
        accepted_records: List[Any] = []
        rejected_items: List[RejectedRecordItem] = []
        rejected_by_reason: Dict[str, int] = {}
        seen_keys: Set[Any] = set()

        for idx, rec in enumerate(records):
            # Check A: DUPLICATE_IN_BATCH
            unique_key = rec.recommendation_id if is_recommendations else (rec.pid, rec.course_id, rec.week_index)
            if unique_key in seen_keys:
                reason = "DUPLICATE_IN_BATCH"
                rejected_items.append(RejectedRecordItem(index=idx, pid=rec.pid, reason_code=reason))
                rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
                continue
            seen_keys.add(unique_key)

            # Check B: UNKNOWN_PID
            if rec.pid not in known_pids:
                reason = "UNKNOWN_PID"
                rejected_items.append(RejectedRecordItem(index=idx, pid=rec.pid, reason_code=reason))
                rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
                continue

            # Check C: NOT_ENROLLED (weekly collections only)
            if not is_recommendations:
                if (rec.pid, str(rec.course_id)) not in enrolled_set:
                    reason = "NOT_ENROLLED"
                    rejected_items.append(RejectedRecordItem(index=idx, pid=rec.pid, reason_code=reason))
                    rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
                    continue

            # Check D: NO_CONSENT (OULAD exempt)
            if rec.pid not in oulad_pids and rec.pid not in consenting_pids:
                reason = "NO_CONSENT"
                rejected_items.append(RejectedRecordItem(index=idx, pid=rec.pid, reason_code=reason))
                rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
                continue

            # Check E: CONFLICT_STAFF_DECISION (recommendations only)
            if is_recommendations:
                rec_id = rec.recommendation_id
                is_staff_decided = False
                if rec_id in decided_outcomes_set:
                    is_staff_decided = True
                elif rec_id in existing_rec_status_map:
                    status_val = existing_rec_status_map[rec_id]
                    if status_val not in {"proposed", "pending"}:
                        is_staff_decided = True

                if is_staff_decided:
                    reason = "CONFLICT_STAFF_DECISION"
                    rejected_items.append(RejectedRecordItem(index=idx, pid=rec.pid, reason_code=reason))
                    rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
                    continue

            accepted_records.append(rec)

        # 6. Prepare documents for storage
        existing_id_map: Dict[Tuple[str, str, int], Any] = {}
        if not is_recommendations and accepted_records:
            batch_pids = list({r.pid for r in accepted_records})
            batch_courses = list({str(r.course_id) for r in accepted_records})
            async for ex_doc in db[target_collection].find(
                {"pid": {"$in": batch_pids}, "course_id": {"$in": batch_courses}},
                {"_id": 1, "pid": 1, "course_id": 1, "week_index": 1},
            ):
                existing_id_map[(ex_doc["pid"], str(ex_doc["course_id"]), int(ex_doc["week_index"]))] = ex_doc["_id"]

        docs_to_persist: List[Dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)

        for rec in accepted_records:
            dumped = rec.model_dump()
            if is_recommendations:
                doc_id = rec.recommendation_id
            else:
                matched_id = existing_id_map.get((rec.pid, str(rec.course_id), int(rec.week_index)))
                doc_id = matched_id if matched_id is not None else f"{rec.pid}_{rec.course_id}_{rec.week_index}"

            # Convert enum keys or values to plain strings for MongoDB compliance
            if "emotion_scores" in dumped and isinstance(dumped["emotion_scores"], dict):
                dumped["emotion_scores"] = {
                    (k.value if hasattr(k, "value") else str(k)): float(v)
                    for k, v in dumped["emotion_scores"].items()
                }
            if "trajectory_label" in dumped and hasattr(dumped["trajectory_label"], "value"):
                dumped["trajectory_label"] = dumped["trajectory_label"].value
            elif "trajectory_label" in dumped:
                dumped["trajectory_label"] = str(dumped["trajectory_label"])

            if "risk_tier" in dumped and hasattr(dumped["risk_tier"], "value"):
                dumped["risk_tier"] = dumped["risk_tier"].value
            elif "risk_tier" in dumped:
                dumped["risk_tier"] = str(dumped["risk_tier"])

            doc = {
                "_id": doc_id,
                **dumped,
                "schema_version": 1,
                "source_version": str(envelope.schema_version),
                "ingested_at": now_utc,
                "ingestion_run_id": run_id,
                "source": source_tag or "ingest",
            }
            docs_to_persist.append(doc)

        # 7. Persistence execution or Dry-Run calculation
        created_count = 0
        updated_count = 0

        if dry_run:
            if docs_to_persist:
                ids_to_check = [d["_id"] for d in docs_to_persist]
                existing_matched = set(
                    await db[target_collection].distinct("_id", {"_id": {"$in": ids_to_check}})
                )
                updated_count = sum(1 for d in docs_to_persist if d["_id"] in existing_matched)
                created_count = len(docs_to_persist) - updated_count
        else:
            if docs_to_persist:
                ops = [
                    ReplaceOne({"_id": d["_id"]}, d, upsert=True)
                    for d in docs_to_persist
                ]
                bulk_res = await db[target_collection].bulk_write(ops, ordered=False)
                created_count = bulk_res.upserted_count
                updated_count = bulk_res.matched_count

        accepted_count = len(accepted_records)
        rejected_count = len(rejected_items)
        run_status = "completed" if rejected_count == 0 else "partial"
        ended_at = datetime.now(timezone.utc)

        run_details: Dict[str, Any] = {
            "endpoint": request.url.path,
            "received": received_count,
            "accepted": accepted_count,
            "rejected": rejected_count,
            "created": created_count,
            "updated": updated_count,
            "rejected_by_reason": rejected_by_reason,
            "envelope_schema_version": str(envelope.schema_version),
            "sender_request_id": str(envelope.request_id),
        }

        # 8. Finalize Ingestion Run record
        await db[col.INGESTION_RUNS].update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "ended_at": ended_at,
                    "status": run_status,
                    "records_processed": received_count,
                    "details": run_details,
                }
            },
        )

        # 9. Non-critical Audit Logging
        try:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.DATA_INGESTED,
                actor_id=actor.actor_id,
                actor_role="component",
                target_type="ingest",
                target_id=request.url.path,
                outcome=AuditOutcome.SUCCESS,
                details={
                    "endpoint": request.url.path,
                    "run_id": run_id,
                    "received": received_count,
                    "accepted": accepted_count,
                    "rejected": rejected_count,
                    "created": created_count,
                    "updated": updated_count,
                    "dry_run": dry_run,
                },
            )
        except Exception as audit_err:
            logger.warning("Failed non-critical DATA_INGESTED audit log write: %s", audit_err)

        return IngestResponse(
            run_id=run_id,
            schema_version=str(envelope.schema_version),
            dry_run=dry_run,
            received=received_count,
            accepted=accepted_count,
            rejected=rejected_count,
            created=created_count,
            updated=updated_count,
            rejected_records=rejected_items,
        )

    except Exception as exc:
        ended_at = datetime.now(timezone.utc)
        await db[col.INGESTION_RUNS].update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "ended_at": ended_at,
                    "status": "failed",
                    "error_message": str(exc),
                }
            },
        )
        raise


# ── Ingestion Endpoints (Strictly POST routes) ────────────────────────────────

@router.post(
    "/affective",
    response_model=IngestResponse,
    summary="Ingest Affective Weekly Vectors (Component 1)",
)
async def ingest_affective(
    request: Request,
    dry_run: bool = Query(default=False),
    source: Optional[str] = Query(default=None, description="Optional provenance tag"),
    actor: IngestActor = Depends(ingest_actor("c1")),
    envelope: Envelope[Any] = Depends(validated_envelope(AffectiveWeeklyVector)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestResponse:
    """Consumes and idempotently stores C1 affective state predictions."""
    return await process_component_ingestion(
        request=request,
        db=db,
        actor=actor,
        envelope=envelope,
        target_collection=col.AFFECTIVE_WEEKLY,
        dry_run=dry_run,
        is_recommendations=False,
        source_tag=source,
    )


@router.post(
    "/trajectory",
    response_model=IngestResponse,
    summary="Ingest Engagement Trajectories (Component 2)",
)
async def ingest_trajectory(
    request: Request,
    dry_run: bool = Query(default=False),
    source: Optional[str] = Query(default=None, description="Optional provenance tag"),
    actor: IngestActor = Depends(ingest_actor("c2")),
    envelope: Envelope[Any] = Depends(validated_envelope(EngagementTrajectory)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestResponse:
    """Consumes and idempotently stores C2 longitudinal engagement classifications."""
    return await process_component_ingestion(
        request=request,
        db=db,
        actor=actor,
        envelope=envelope,
        target_collection=col.ENGAGEMENT_TRAJECTORIES,
        dry_run=dry_run,
        is_recommendations=False,
        source_tag=source,
    )


@router.post(
    "/risk",
    response_model=IngestResponse,
    summary="Ingest Risk Assessments (Component 3)",
)
async def ingest_risk(
    request: Request,
    dry_run: bool = Query(default=False),
    source: Optional[str] = Query(default=None, description="Optional provenance tag"),
    actor: IngestActor = Depends(ingest_actor("c3")),
    envelope: Envelope[Any] = Depends(validated_envelope(RiskAssessment)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestResponse:
    """Consumes and idempotently stores C3 multimodal risk tiers and predictions."""
    return await process_component_ingestion(
        request=request,
        db=db,
        actor=actor,
        envelope=envelope,
        target_collection=col.RISK_ASSESSMENTS,
        dry_run=dry_run,
        is_recommendations=False,
        source_tag=source,
    )


@router.post(
    "/recommendations",
    response_model=IngestResponse,
    summary="Ingest Intervention Recommendations (Component 4)",
)
async def ingest_recommendations(
    request: Request,
    dry_run: bool = Query(default=False),
    source: Optional[str] = Query(default=None, description="Optional provenance tag"),
    actor: IngestActor = Depends(ingest_actor("c4")),
    envelope: Envelope[Any] = Depends(validated_envelope(InterventionRecommendation)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestResponse:
    """Consumes and idempotently stores C4 ranked adaptive intervention suggestions."""
    return await process_component_ingestion(
        request=request,
        db=db,
        actor=actor,
        envelope=envelope,
        target_collection=col.RECOMMENDATIONS,
        dry_run=dry_run,
        is_recommendations=True,
        source_tag=source,
    )
