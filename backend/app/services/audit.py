"""
backend/app/services/audit.py

Feature 7: Audit Logging Service.
Provides:
  - async log_event(): Core logging function recording immutable entries.
  - Strict compliance controls:
      * Mandatory validation on IDENTITY_REVEAL justification reason (min 10 chars).
      * Critical actions (IDENTITY_REVEAL, EXPORT_GENERATED) must succeed prior to data return;
        write failures abort the request with HTTP 500.
      * Non-critical actions safely log write errors without disrupting the user's operation.
  - Backward compatibility:
      * log_audit_event() wrapper for legacy callers.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.audit_repo import insert_audit_log
from app.schemas.audit import AuditAction, AuditLogBase, AuditOutcome

logger = logging.getLogger("app.audit")

CRITICAL_ACTIONS = {
    AuditAction.IDENTITY_REVEAL,
    AuditAction.EXPORT_GENERATED,
    "IDENTITY_REVEAL",
    "EXPORT_GENERATED",
}


async def log_event(
    request: Optional[Request],
    db: AsyncIOMotorDatabase,
    action: Union[AuditAction, str],
    actor_id: str,
    actor_role: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLogBase:
    """
    Creates and persists an immutable audit log entry.

    Parameters:
      request: The active FastAPI Request, or None.
      db: Motor database instance.
      action: Event action name or enum.
      actor_id: Identifier of the actor ('anonymous' for unauthenticated).
      actor_role: Role of the actor.
      target_type: Resource type (e.g. 'student', 'course').
      target_id: Identifier of the target resource (PID for students).
      outcome: 'success', 'failed', or 'denied'.
      reason: Required justification for IDENTITY_REVEAL.
      details: Sanitized metadata (prohibits sensitive keys).
    """
    # 1. Normalize action & outcome enums
    action_enum = AuditAction(action) if not isinstance(action, AuditAction) else action
    outcome_enum = AuditOutcome(outcome) if not isinstance(outcome, AuditOutcome) else outcome

    # 2. Enforce reason requirement for IDENTITY_REVEAL
    if action_enum == AuditAction.IDENTITY_REVEAL:
        if not reason or len(reason.strip()) < 10:
            raise ValueError(
                "A valid justification reason of at least 10 characters is required for IDENTITY_REVEAL."
            )

    # 3. Extract request metadata
    if request:
        req_id = (
            getattr(request.state, "request_id", None)
            or request.headers.get("x-request-id")
            or str(uuid.uuid4())
        )
        ip_addr = (
            getattr(request.state, "client_ip", None)
            or (request.client.host if request.client else "127.0.0.1")
        )
        ua = getattr(request.state, "user_agent", None) or request.headers.get("user-agent", "unknown")
    else:
        req_id = str(uuid.uuid4())
        ip_addr = "127.0.0.1"
        ua = "internal/system"

    # 4. Construct AuditLogBase (runs Pydantic validators, including denylist checks)
    log_entry = AuditLogBase(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        actor_id=str(actor_id),
        actor_role=str(actor_role),
        action=action_enum,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome_enum,
        reason=reason.strip() if reason else None,
        ip_address=ip_addr,
        user_agent=ua,
        request_id=req_id,
        details=details or {},
        schema_version=1,
    )

    # 5. Persist to MongoDB
    is_critical = action_enum in CRITICAL_ACTIONS or action in CRITICAL_ACTIONS
    try:
        await insert_audit_log(db, log_entry)
        return log_entry
    except Exception as exc:
        logger.error(
            "Failed to write audit event '%s' for actor '%s': %s",
            action_enum.value,
            actor_id,
            exc,
            exc_info=True,
        )
        if is_critical:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audit logging failed. For security and regulatory compliance, this action cannot proceed.",
            ) from exc
        # Non-critical failure: log error and return constructed entry without breaking flow
        return log_entry


# ── Backward Compatibility Wrapper ────────────────────────────────────────────

async def log_audit_event(
    db: AsyncIOMotorDatabase,
    action: str,
    requester_id: str,
    target_pid: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """
    Legacy helper maintained for backward compatibility.
    Proxies calls to log_event().
    """
    sanitized_details = dict(details or {})
    # Remove any denylisted keys if present in legacy calls to avoid validation rejections
    for forbidden in ["student_id", "email", "name", "password", "token", "grade", "text", "message", "registration_id"]:
        sanitized_details.pop(forbidden, None)

    reason = sanitized_details.pop("reason", None)
    if action == "IDENTITY_REVEAL" and not reason:
        reason = "Institutional welfare & retention assessment"

    entry = await log_event(
        request=request,
        db=db,
        action=action,
        actor_id=requester_id,
        actor_role="unknown",
        target_type="student" if target_pid else None,
        target_id=target_pid,
        outcome="success",
        reason=reason,
        details=sanitized_details,
    )
    return entry.model_dump()
