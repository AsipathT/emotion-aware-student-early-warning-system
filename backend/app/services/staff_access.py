"""
backend/app/services/staff_access.py

Feature 30 & Foundation for Features 31-39: Shared Staff Workspace Access Control.
Provides:
  - require_staff: Role gate allowing 'counsellor' and 'admin' only.
  - validate_pid: Validates STU_xxxxxxxx format with HTTP 422 on failure.
  - is_pid_visible: Verified against active research consent (via get_eligible_consenting_pids).
  - audit_student_view: Tamper-resistant critical audit logging with fail-closed guarantee (HTTP 500).
"""

import logging
from typing import Any, Dict, Optional, Set

from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_current_user
from app.core.privacy import is_valid_pid
from app.models.user import User, UserRole
from app.routers.export import get_eligible_consenting_pids
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event

logger = logging.getLogger("app.services.staff_access")

STAFF_ROLES = frozenset({UserRole.COUNSELLOR, UserRole.ADMIN, "counsellor", "admin"})


def require_staff_role(user: User) -> User:
    """Verifies that the provided user possesses counsellor or admin role."""
    role = getattr(user, "role", None)
    if role not in STAFF_ROLES and getattr(role, "value", None) not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Counsellor or Administrator privileges required.",
        )
    return user


async def require_staff(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency requiring counsellor or admin role."""
    return require_staff_role(user)


def validate_pid(pid: str) -> str:
    """
    Validates that a student pseudonym ID adheres to the Feature 5 STU_xxxxxxxx format.
    Raises HTTP 422 if invalid.
    """
    if not pid or not is_valid_pid(str(pid)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid student pseudonym ID (PID) '{pid}'. Must follow format: STU_ followed by 8 hex characters.",
        )
    return str(pid).strip()


async def is_pid_visible(
    db: AsyncIOMotorDatabase,
    pid: str,
    eligible_cache: Optional[Set[str]] = None,
) -> bool:
    """
    Determines if a student's data is visible to staff based on active research consent.
    Uses get_eligible_consenting_pids to guarantee exact parity with export rules.
    Accepts an optional per-request set cache to prevent redundant aggregations.
    """
    clean_pid = str(pid).strip()
    if eligible_cache is not None:
        return clean_pid in eligible_cache

    eligible_pids = await get_eligible_consenting_pids(db)
    return clean_pid in eligible_pids


async def audit_student_view(
    request: Optional[Request],
    db: AsyncIOMotorDatabase,
    user: User,
    *,
    pid: str,
    view: str,
    course_id: Optional[str] = None,
    week_index: Optional[int] = None,
) -> None:
    """
    Records an immutable audit log entry when staff views student analytics.
    Fails closed (HTTP 500) if the audit log write fails, ensuring zero data leakage
    without complete compliance traceability.
    """
    details: Dict[str, Any] = {
        "view": str(view),
        "requester_role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }
    if course_id:
        details["course_id"] = str(course_id).strip()
    if week_index is not None:
        details["week_index"] = int(week_index)

    actor_id = str(user.id)
    actor_role = user.role.value if hasattr(user.role, "value") else str(user.role)

    try:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.STUDENT_DATA_VIEWED,
            actor_id=actor_id,
            actor_role=actor_role,
            target_type="student",
            target_id=str(pid).strip(),
            outcome=AuditOutcome.SUCCESS,
            details=details,
        )
    except Exception as exc:
        logger.error(
            "Audit logging failed for staff student view (actor=%s, pid=%s, view=%s): %s",
            actor_id,
            pid,
            view,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit logging failed. For regulatory compliance, student analytics cannot be displayed.",
        ) from exc
