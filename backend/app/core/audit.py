"""
backend/app/core/audit.py

Feature 7: Reusable FastAPI Dependency Factory for Audit Logging.
Allows route handlers to inject automated audit logging declaratively:
    dependencies=[Depends(audit(AuditAction.AUDIT_LOG_VIEWED))]
"""

from typing import Callable, Optional, Union
from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event


def audit(
    action: Union[AuditAction, str],
    target_param: Optional[str] = None,
    target_type: Optional[str] = None,
) -> Callable:
    """
    FastAPI dependency factory that resolves the authenticated actor and
    records an audit event before the endpoint returns.

    Parameters:
      action: AuditAction enum or string identifier.
      target_param: Optional path or query parameter name representing the target resource.
      target_type: Optional resource category (e.g. 'student', 'course').
    """
    async def _audit_dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> None:
        target_id = None
        if target_param:
            target_id = (
                request.path_params.get(target_param)
                or request.query_params.get(target_param)
            )

        role_str = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )

        inferred_target_type = target_type
        if not inferred_target_type and target_param in ("pid", "student_id"):
            inferred_target_type = "student"

        await log_event(
            request=request,
            db=db,
            action=action,
            actor_id=str(current_user.id),
            actor_role=role_str,
            target_type=inferred_target_type,
            target_id=target_id,
            outcome=AuditOutcome.SUCCESS,
        )

    return _audit_dependency
