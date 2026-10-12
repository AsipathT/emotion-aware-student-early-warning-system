"""
backend/app/routers/pipeline.py

Feature 22: Weekly Scheduler & Pipeline Orchestration API.
Endpoints:
  - GET  /api/v1/pipeline/ready                     -> Component polling for ready stages
  - GET  /api/v1/pipeline/runs                      -> List & filter pipeline runs (Admin/Auditor)
  - GET  /api/v1/pipeline/runs/{course_id}/{week}   -> Get run details (Admin/Auditor)
  - POST /api/v1/pipeline/trigger                   -> Manual trigger with force & conflict handling (Admin)
  - POST /api/v1/pipeline/runs/{course_id}/{week}/advance -> Step an active run (Admin)
  - GET  /api/v1/pipeline/status                    -> Scheduler diagnostics (Admin/Auditor)
"""

import hmac
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.component_auth import ExportActor
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_admin, require_roles
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db import collections as col
from app.models.user import User, UserRole
from app.pipeline.advance import advance_pipeline_run
from app.pipeline.clock import get_clock
from app.pipeline.discovery import create_pipeline_run
from app.pipeline.scheduler import get_pipeline_scheduler_status
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event

logger = logging.getLogger("app.routers.pipeline")

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


# ── Component & Pipeline Actor Authentication ─────────────────────────────────

async def authenticate_pipeline_actor(
    request: Request,
    x_component_key: Optional[str] = Header(None, alias="X-Component-Key"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ExportActor:
    """
    Authorizes either:
    1. A downstream component client providing 'X-Component-Key'
    2. An administrator providing a Bearer JWT
    """
    keys_map = settings.COMPONENT_API_KEYS

    # 1. Check for Admin Bearer token first
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            payload = decode_token(token)
            if payload.get("type") == ACCESS_TOKEN_TYPE:
                sub = payload.get("sub")
                if sub:
                    user_doc = await db.users.find_one({"_id": str(sub)}) or await db.users.find_one({"id": str(sub)})
                    if user_doc and user_doc.get("is_active", True) and user_doc.get("role") == UserRole.ADMIN:
                        return ExportActor(
                            actor_id=str(user_doc.get("_id", sub)),
                            role="admin",
                            is_admin=True,
                        )
        except Exception:
            pass

    # 2. Check X-Component-Key
    if not keys_map:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component API keys are not configured on this server.",
        )

    if not x_component_key:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.ACCESS_DENIED,
            actor_id="anonymous",
            actor_role="unknown",
            target_type="pipeline",
            target_id=request.url.path,
            outcome=AuditOutcome.DENIED,
            reason="Missing X-Component-Key header and no valid admin Bearer token.",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Component-Key header or valid Admin Bearer token.",
        )

    matched_comp: Optional[str] = None
    for comp_name, secret_key in keys_map.items():
        if hmac.compare_digest(x_component_key.encode("utf-8"), secret_key.encode("utf-8")):
            matched_comp = comp_name
            break

    if not matched_comp:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.ACCESS_DENIED,
            actor_id="anonymous",
            actor_role="unknown",
            target_type="pipeline",
            target_id=request.url.path,
            outcome=AuditOutcome.DENIED,
            reason="Invalid component API key.",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid component API key.",
        )

    return ExportActor(
        actor_id=f"component:{matched_comp}",
        role="component",
        is_admin=False,
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    course_id: str = Field(..., min_length=1, description="Target course identifier")
    week_index: int = Field(..., ge=0, description="Academic week index")
    force: bool = Field(default=False, description="Force rerun even if existing run is active or completed")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/ready",
    summary="Poll for Ready Pipeline Stages",
    description="Returns courses and weeks where the specified component stage is ready for input.",
)
async def get_ready_stages(
    component: Optional[str] = Query(None, description="Component name: c1, c2, c3, or c4"),
    course_id: Optional[str] = Query(None, description="Filter by course identifier"),
    week_index: Optional[int] = Query(None, ge=0, description="Filter by week index"),
    actor: ExportActor = Depends(authenticate_pipeline_actor),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """
    Component polling endpoint. Returns list of course/week units ready for component consumption.
    Zero student PII is exposed.
    """
    # If caller is a component and not an admin, resolve/verify component scope
    target_comp = component
    if not actor.is_admin:
        actor_comp = actor.actor_id.replace("component:", "").lower()
        if target_comp is None:
            target_comp = actor_comp
        elif target_comp.lower() != actor_comp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Component key for '{actor_comp}' cannot query ready status for '{target_comp}'.",
            )
    else:
        if target_comp is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Component query parameter (c1, c2, c3, or c4) is required.",
            )

    target_comp = target_comp.lower()
    if target_comp not in ("c1", "c2", "c3", "c4"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid component '{target_comp}'. Allowed values: c1, c2, c3, c4.",
        )

    # Query pipeline runs where stages.<target_comp>.status is 'ready' or 'receiving'
    query: Dict[str, Any] = {
        f"stages.{target_comp}.status": {"$in": ["ready", "receiving"]},
    }
    if course_id:
        query["course_id"] = course_id
    if week_index is not None:
        query["week_index"] = week_index

    cursor = db[col.PIPELINE_RUNS].find(query).sort([("started_at", 1)])
    runs = await cursor.to_list(length=200)

    items = []
    for r in runs:
        stage_info = r.get("stages", {}).get(target_comp, {})
        items.append({
            "course_id": r["course_id"],
            "week_index": r["week_index"],
            "run_id": r["run_id"],
            "stage": target_comp,
            "status": stage_info.get("status"),
            "since": stage_info.get("since"),
            "eligible": stage_info.get("eligible", 0),
            "received": stage_info.get("received", 0),
            "coverage": stage_info.get("coverage"),
            "notified_at": stage_info.get("notified_at"),
        })

    return {
        "component": target_comp,
        "count": len(items),
        "items": items,
    }


@router.get(
    "/runs",
    summary="List Pipeline Runs",
    description="Lists and filters pipeline execution runs. Restricted to Admins and Auditors.",
)
async def list_pipeline_runs(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    week_index: Optional[int] = Query(None, ge=0, description="Filter by week index"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by run status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Admin/Auditor view of historical and running pipeline orchestrations."""
    query: Dict[str, Any] = {}
    if course_id:
        query["course_id"] = course_id
    if week_index is not None:
        query["week_index"] = week_index
    if status_filter:
        query["status"] = status_filter.lower()

    total = await db[col.PIPELINE_RUNS].count_documents(query)
    skip = (page - 1) * page_size

    cursor = db[col.PIPELINE_RUNS].find(query, {"_id": 0}).sort([("started_at", -1)]).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get(
    "/runs/{course_id}/{week_index}",
    summary="Get Specific Pipeline Run",
    description="Retrieves a single pipeline run by course ID and week index. Restricted to Admins and Auditors.",
)
async def get_pipeline_run(
    course_id: str,
    week_index: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves detailed stage state for a specific course week."""
    run_doc = await db[col.PIPELINE_RUNS].find_one(
        {"course_id": course_id, "week_index": week_index},
        {"_id": 0},
    )
    if not run_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found for course '{course_id}' week {week_index}.",
        )
    return run_doc


@router.post(
    "/trigger",
    summary="Manually Trigger Pipeline Run",
    description="Manually triggers or resets a pipeline run for a course and week. Admin only.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_pipeline_run(
    request: Request,
    payload: TriggerRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Manually creates and kicks off a pipeline run."""
    course_id = payload.course_id
    week_index = payload.week_index
    force = payload.force

    # 1. Verify course week exists
    cw = await db[col.COURSE_WEEKS].find_one({"course_id": course_id, "week_index": week_index})
    if not cw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course week not found for course '{course_id}' week {week_index}.",
        )

    # 2. Check existing run
    existing = await db[col.PIPELINE_RUNS].find_one({"course_id": course_id, "week_index": week_index})
    if existing:
        if not force:
            existing_status = existing.get("status")
            if existing_status in ("pending", "running"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Pipeline run already active for course '{course_id}' week {week_index}.",
                )
            elif existing_status == "complete":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Pipeline run already completed for course '{course_id}' week {week_index}. Use force=true to rerun.",
                )
        # If force=True, remove existing run document so we can re-create cleanly
        await db[col.PIPELINE_RUNS].delete_one({"course_id": course_id, "week_index": week_index})

    now = get_clock()
    admin_id = str(admin.id)
    admin_role = admin.role.value if hasattr(admin.role, "value") else str(admin.role)

    # Audit PIPELINE_TRIGGERED
    await log_event(
        request=request,
        db=db,
        action=AuditAction.PIPELINE_TRIGGERED,
        actor_id=admin_id,
        actor_role=admin_role,
        target_type="pipeline_run",
        target_id=f"{course_id}_w{week_index}",
        outcome=AuditOutcome.SUCCESS,
        details={"course_id": course_id, "week_index": week_index, "force": force},
    )

    # Create run
    run_doc = await create_pipeline_run(
        db=db,
        course_id=course_id,
        week_index=week_index,
        week_end=cw["end_date"],
        trigger="manual",
        triggered_by=f"admin:{admin.email}",
        now=now,
    )

    if not run_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concurrent creation conflict for course '{course_id}' week {week_index}.",
        )

    # Step the run through initial progression
    updated_run = await advance_pipeline_run(db=db, run=run_doc, now=now)
    # Remove _id if present for clean JSON
    updated_run.pop("_id", None)

    return {
        "status": "accepted",
        "message": f"Pipeline run initiated for course '{course_id}' week {week_index}.",
        "run": updated_run,
    }


@router.post(
    "/runs/{course_id}/{week_index}/advance",
    summary="Advance Specific Pipeline Run",
    description="Manually triggers progression evaluation for an active pipeline run. Admin only.",
)
async def advance_specific_run(
    course_id: str,
    week_index: int,
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Steps an existing pipeline run forward through its stage machine."""
    run_doc = await db[col.PIPELINE_RUNS].find_one({"course_id": course_id, "week_index": week_index})
    if not run_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found for course '{course_id}' week {week_index}.",
        )

    now = get_clock()
    updated = await advance_pipeline_run(db=db, run=run_doc, now=now)
    updated.pop("_id", None)

    return {
        "status": "success",
        "message": f"Pipeline run advanced for course '{course_id}' week {week_index}.",
        "run": updated,
    }


@router.get(
    "/status",
    summary="Get Scheduler and Pipeline Status",
    description="Returns scheduler heartbeat, execution statistics, and latest run summary. Admin/Auditor.",
)
async def get_pipeline_scheduler_diagnostics(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Returns scheduler operational status and recent run statistics."""
    sched_info = get_pipeline_scheduler_status()

    latest_run = await db[col.PIPELINE_RUNS].find_one(
        {},
        {"_id": 0},
        sort=[("started_at", -1)],
    )

    total_runs = await db[col.PIPELINE_RUNS].count_documents({})
    running_runs = await db[col.PIPELINE_RUNS].count_documents({"status": "running"})
    complete_runs = await db[col.PIPELINE_RUNS].count_documents({"status": "complete"})
    partial_runs = await db[col.PIPELINE_RUNS].count_documents({"status": "partial"})
    failed_runs = await db[col.PIPELINE_RUNS].count_documents({"status": "failed"})

    return {
        "scheduler": sched_info,
        "latest_run": latest_run,
        "counts": {
            "total": total_runs,
            "running": running_runs,
            "complete": complete_runs,
            "partial": partial_runs,
            "failed": failed_runs,
        },
    }
