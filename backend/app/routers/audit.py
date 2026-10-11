"""
backend/app/routers/audit.py

Feature 7: Audit Log Query & Compliance Export Router.
Restricted exclusively to users with the Admin and Auditor roles.
Strictly read-only: Contains no POST, PUT, PATCH, or DELETE routes.
Provides:
  - GET /api/v1/audit: Filterable paginated query of immutable audit events.
  - GET /api/v1/audit/export: Streaming CSV export with row capping and formula sanitization.
"""

import csv
import io
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.repositories.audit_repo import find_audit_logs_paginated, stream_audit_logs
from app.schemas.audit import (
    AuditAction,
    AuditLogBase,
    AuditLogQueryResponse,
    AuditOutcome,
)
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

MAX_EXPORT_ROWS = 5000


def _build_audit_query(
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    action: Optional[AuditAction] = None,
    outcome: Optional[AuditOutcome] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Builds MongoDB query filter dictionary."""
    query: Dict[str, Any] = {}

    if actor_id:
        query["actor_id"] = actor_id.strip()

    if target_id:
        query["target_id"] = target_id.strip()

    if action:
        query["action"] = action.value if hasattr(action, "value") else str(action)

    if outcome:
        query["outcome"] = outcome.value if hasattr(outcome, "value") else str(outcome)

    if start_date or end_date:
        time_query: Dict[str, Any] = {}
        if start_date:
            time_query["$gte"] = start_date
        if end_date:
            time_query["$lte"] = end_date
        query["timestamp"] = time_query

    return query


def _sanitize_csv_cell(value: Any) -> str:
    """
    Prevents CSV formula injection by prepending a single quote
    if the string value starts with =, +, -, @, or tab/return.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        str_val = json.dumps(value)
    else:
        str_val = str(value)

    if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{str_val}"
    return str_val


# ── GET /api/v1/audit ─────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=AuditLogQueryResponse,
    summary="Query audit log entries (Admin & Auditor only)",
    description=(
        "Retrieves a paginated list of immutable audit log entries with optional filters. "
        "Strictly restricted to Admin and Auditor roles. Every access records an AUDIT_LOG_VIEWED event."
    ),
)
async def query_audit_logs(
    request: Request,
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    target_id: Optional[str] = Query(None, description="Filter by target ID (or PID)"),
    action: Optional[AuditAction] = Query(None, description="Filter by action"),
    outcome: Optional[AuditOutcome] = Query(None, description="Filter by outcome"),
    start_date: Optional[datetime] = Query(None, description="Filter from timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter to timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AuditLogQueryResponse:
    query = _build_audit_query(
        actor_id=actor_id,
        target_id=target_id,
        action=action,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
    )

    skip = (page - 1) * limit
    raw_records, total = await find_audit_logs_paginated(db, query, skip=skip, limit=limit)

    items = [AuditLogBase(**r) for r in raw_records]
    pages = (total + limit - 1) // limit if total > 0 else 1

    # Log the view action (filters recorded, not the data)
    filters_summary = {
        "filtered_actor_id": actor_id,
        "filtered_target_id": target_id,
        "filtered_action": action.value if action else None,
        "filtered_outcome": outcome.value if outcome else None,
        "page": page,
        "limit": limit,
    }
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    await log_event(
        request=request,
        db=db,
        action=AuditAction.AUDIT_LOG_VIEWED,
        actor_id=str(current_user.id),
        actor_role=role_str,
        outcome=AuditOutcome.SUCCESS,
        details={"filters": filters_summary, "matched_count": total},
    )

    return AuditLogQueryResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


# ── GET /api/v1/audit/export ──────────────────────────────────────────────────

@router.get(
    "/export",
    summary="Export audit logs to CSV (Admin & Auditor only)",
    description=(
        "Streams a CSV export of audit logs matching query criteria. "
        "Enforces formula sanitization and row limits. "
        "Requires critical audit logging of EXPORT_GENERATED prior to data stream return."
    ),
)
async def export_audit_logs(
    request: Request,
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    target_id: Optional[str] = Query(None, description="Filter by target ID"),
    action: Optional[AuditAction] = Query(None, description="Filter by action"),
    outcome: Optional[AuditOutcome] = Query(None, description="Filter by outcome"),
    start_date: Optional[datetime] = Query(None, description="Filter from timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter to timestamp"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StreamingResponse:
    query = _build_audit_query(
        actor_id=actor_id,
        target_id=target_id,
        action=action,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
    )

    total_matches = await db.audit_logs.count_documents(query)
    effective_count = min(total_matches, MAX_EXPORT_ROWS)

    # Critical action: EXPORT_GENERATED must succeed before returning stream
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    filters_summary = {
        "filtered_actor_id": actor_id,
        "filtered_target_id": target_id,
        "filtered_action": action.value if action else None,
        "filtered_outcome": outcome.value if outcome else None,
    }

    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=str(current_user.id),
        actor_role=role_str,
        outcome=AuditOutcome.SUCCESS,
        details={"filters": filters_summary, "row_count": effective_count},
    )

    # Stream CSV generator
    async def csv_generator() -> AsyncGenerator[str, None]:
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        headers = [
            "id",
            "timestamp",
            "actor_id",
            "actor_role",
            "action",
            "target_type",
            "target_id",
            "outcome",
            "reason",
            "ip_address",
            "user_agent",
            "request_id",
            "details",
        ]
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Stream documents
        async for doc in stream_audit_logs(db, query, limit=MAX_EXPORT_ROWS):
            row = [
                _sanitize_csv_cell(doc.get("id")),
                _sanitize_csv_cell(doc.get("timestamp")),
                _sanitize_csv_cell(doc.get("actor_id")),
                _sanitize_csv_cell(doc.get("actor_role")),
                _sanitize_csv_cell(doc.get("action")),
                _sanitize_csv_cell(doc.get("target_type")),
                _sanitize_csv_cell(doc.get("target_id")),
                _sanitize_csv_cell(doc.get("outcome")),
                _sanitize_csv_cell(doc.get("reason")),
                _sanitize_csv_cell(doc.get("ip_address")),
                _sanitize_csv_cell(doc.get("user_agent")),
                _sanitize_csv_cell(doc.get("request_id")),
                _sanitize_csv_cell(doc.get("details")),
            ]
            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"audit_log_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
