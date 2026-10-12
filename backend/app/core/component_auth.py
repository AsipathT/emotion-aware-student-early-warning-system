"""
backend/app/core/component_auth.py

Feature 21 (Part B): Component API Authentication and Authorization.
Provides:
  - export_actor(scope: str): FastAPI dependency enforcing component API key authentication
    via 'X-Component-Key' header or Admin Bearer token.
  - Enforces constant-time hmac.compare_digest verification.
  - Generates Feature 7 audit log entries on authorization failure (ACCESS_DENIED).
  - Validates scopes: c1 -> messages, c2 -> behavior, c3 -> academic.
"""

import hmac
import logging
from typing import Callable, Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, Header, Request, status
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_db
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.models.user import UserRole
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_event

logger = logging.getLogger("app.component_auth")


class ExportActor(BaseModel):
    """Actor identity representing a component client or testing admin."""
    actor_id: str
    role: str
    is_admin: bool = False


EXPORT_SCOPE_MAP: dict[str, set[str]] = {
    "messages": {"c1"},
    "c1": {"c1"},
    "behavior": {"c2"},
    "c2": {"c2"},
    "academic": {"c3"},
    "c3": {"c3"},
    "affective": {"c3", "c4"},
    "trajectory": {"c3", "c4"},
    "risk": {"c4"},
    "outcomes": {"c4"},
}


def export_actor(scope: str) -> Callable:
    """
    Factory creating a dependency that authorizes component API access for `scope`.
    Accepts:
      1. 'X-Component-Key' header matching configured secret key for the requested scope.
         Supported scopes map to allowed component sets (e.g. affective -> {c3, c4}).
      2. Authenticated Admin user Bearer JWT token (for verification/testing).
    Raises:
      - 503 Service Unavailable if COMPONENT_API_KEYS is not configured.
      - 401 Unauthorized if key is missing, invalid, or bearer token is invalid.
      - 403 Forbidden if key belongs to an unauthorized component scope.
    """
    target_scope = scope.lower().strip()
    allowed_components = EXPORT_SCOPE_MAP.get(target_scope, {target_scope})

    async def _authenticate(
        request: Request,
        x_component_key: Optional[str] = Header(None, alias="X-Component-Key"),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> ExportActor:
        keys_map = settings.COMPONENT_API_KEYS

        # 1. Verify that component keys are configured
        if not keys_map:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Component export API keys are not configured on this server.",
            )

        # 2. Check for optional Admin Bearer token
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
            except JWTError:
                pass

        # 3. Check X-Component-Key
        if not x_component_key:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id="anonymous",
                actor_role="unknown",
                target_type="export",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason="Missing X-Component-Key header and no valid admin Bearer token.",
                details={"endpoint": request.url.path, "required_scope": target_scope},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Component-Key header or valid Admin Bearer token.",
            )

        # Constant-time comparison across configured component keys
        matched_scope: Optional[str] = None
        for comp_name, secret_key in keys_map.items():
            if hmac.compare_digest(x_component_key.encode("utf-8"), secret_key.encode("utf-8")):
                matched_scope = comp_name
                break

        if not matched_scope:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id="anonymous",
                actor_role="unknown",
                target_type="export",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason="Invalid component API key.",
                details={"endpoint": request.url.path, "required_scope": target_scope},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid component API key.",
            )

        # 4. Check scope matching
        if matched_scope not in allowed_components:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id=f"component:{matched_scope}",
                actor_role="component",
                target_type="export",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason=f"Component key scope '{matched_scope}' not authorized for scope '{target_scope}'.",
                details={
                    "endpoint": request.url.path,
                    "matched_scope": matched_scope,
                    "required_scope": target_scope,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Component '{matched_scope}' is not authorized to access '{target_scope}' export.",
            )

        return ExportActor(
            actor_id=f"component:{matched_scope}",
            role="component",
            is_admin=False,
        )

    return _authenticate


class IngestActor(BaseModel):
    """Actor identity representing an authenticated ML component client for data writes."""
    actor_id: str
    component: str


INGEST_SCOPE_MAP = {
    "affective": "c1",
    "c1": "c1",
    "trajectory": "c2",
    "c2": "c2",
    "risk": "c3",
    "c3": "c3",
    "recommendations": "c4",
    "c4": "c4",
}


def ingest_actor(scope: str) -> Callable:
    """
    Factory creating a dependency that authorizes component API write access for `scope`.
    Accepts:
      - 'X-Component-Key' header matching configured secret key for the requested scope.
      - Strictly NO admin Bearer token fallback for write endpoints.
    Raises:
      - 503 Service Unavailable if COMPONENT_API_KEYS is not configured.
      - 401 Unauthorized if key is missing or invalid.
      - 403 Forbidden if key belongs to another component scope.
    """
    raw_scope = scope.lower().strip()
    target_scope = INGEST_SCOPE_MAP.get(raw_scope, raw_scope)

    async def _authenticate(
        request: Request,
        x_component_key: Optional[str] = Header(None, alias="X-Component-Key"),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> IngestActor:
        keys_map = settings.COMPONENT_API_KEYS

        # 1. Verify that component keys are configured
        if not keys_map:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Component API keys are not configured on this server.",
            )

        # 2. Ingestion requires X-Component-Key header (no Bearer token allowed)
        if not x_component_key:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id="anonymous",
                actor_role="unknown",
                target_type="ingest",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason="Missing X-Component-Key header for component ingestion.",
                details={"endpoint": request.url.path, "required_scope": target_scope},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Component-Key header for component ingestion.",
            )

        # 3. Constant-time comparison across configured component keys
        matched_scope: Optional[str] = None
        for comp_name, secret_key in keys_map.items():
            if hmac.compare_digest(x_component_key.encode("utf-8"), secret_key.encode("utf-8")):
                matched_scope = comp_name
                break

        if not matched_scope:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id="anonymous",
                actor_role="unknown",
                target_type="ingest",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason="Invalid component API key for ingestion.",
                details={"endpoint": request.url.path, "required_scope": target_scope},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid component API key.",
            )

        # 4. Scope matching
        if matched_scope != target_scope:
            await log_event(
                request=request,
                db=db,
                action=AuditAction.ACCESS_DENIED,
                actor_id=f"component:{matched_scope}",
                actor_role="component",
                target_type="ingest",
                target_id=request.url.path,
                outcome=AuditOutcome.DENIED,
                reason=f"Component key scope '{matched_scope}' not authorized for ingestion scope '{target_scope}'.",
                details={
                    "endpoint": request.url.path,
                    "matched_scope": matched_scope,
                    "required_scope": target_scope,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Component '{matched_scope}' is not authorized to ingest into '{target_scope}' endpoint.",
            )

        return IngestActor(
            actor_id=f"component:{matched_scope}",
            component=matched_scope,
        )

    return _authenticate


def validate_component_api_keys(keys_map: Optional[dict[str, str]], app_env: str) -> None:
    """
    Validates component API keys at startup:
    - If unconfigured, logs a clear warning.
    - If any key is empty, shorter than 24 characters, or contains 'change_in_production':
      * In production (app_env in {'production', 'prod'}), raises RuntimeError refusing to start.
      * In development/testing, logs a clear warning.
    """
    if not keys_map:
        logger.warning(
            "COMPONENT_API_KEYS is not configured. Component export/ingest endpoints will return HTTP 503."
        )
        return

    is_prod = str(app_env).lower().strip() in {"production", "prod"}
    issues: list[str] = []

    for comp, key in keys_map.items():
        if not key:
            issues.append(f"Component '{comp}' key is empty.")
        elif len(key) < 24:
            issues.append(f"Component '{comp}' key length ({len(key)}) is shorter than 24 characters.")
        elif "change_in_production" in key.lower():
            issues.append(f"Component '{comp}' key contains placeholder 'change_in_production'.")

    if issues:
        summary = "Insecure COMPONENT_API_KEYS configuration detected: " + "; ".join(issues)
        if is_prod:
            logger.error("[STARTUP REJECTED] %s", summary)
            raise RuntimeError(f"Startup rejected in production: {summary}")
        else:
            logger.warning("[STARTUP WARNING] %s", summary)

