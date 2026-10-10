"""
backend/app/schemas/audit.py

Feature 7: Immutable and Privacy-Preserving Audit Log schemas.
Enforces:
  - Strictly typed AuditAction and AuditOutcome enums.
  - Mandatory pseudonymization for student targets (PID format STU_xxxxxxxx).
  - Mandatory >= 10 character justification reason for IDENTITY_REVEAL.
  - Strict recursive denylist validation prohibiting raw sensitive data keys
    (text, message, password, token, grade, email, name, student_id, registration_id).
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ── Action & Outcome Enums ────────────────────────────────────────────────────

class AuditAction(str, Enum):
    """Supported audit log actions."""
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"
    IDENTITY_REVEAL = "IDENTITY_REVEAL"
    CONSENT_ACCEPTED = "CONSENT_ACCEPTED"
    CONSENT_DECLINED = "CONSENT_DECLINED"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
    AUDIT_LOG_VIEWED = "AUDIT_LOG_VIEWED"
    EXPORT_GENERATED = "EXPORT_GENERATED"


class AuditOutcome(str, Enum):
    """Outcome status of the audited action."""
    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"


# ── Sensitive Key Denylist ───────────────────────────────────────────────────

SENSITIVE_KEY_DENYLIST = frozenset({
    "text",
    "message",
    "password",
    "token",
    "grade",
    "email",
    "name",
    "student_id",
    "registration_id",
})


def _validate_no_sensitive_keys(data: Any, path: str = "") -> None:
    """Recursively checks a dictionary or nested structure against the sensitive key denylist."""
    if isinstance(data, dict):
        for key, val in data.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in SENSITIVE_KEY_DENYLIST:
                raise ValueError(
                    f"Sensitive key '{key}' is prohibited in audit log details to prevent raw PII leakage."
                )
            _validate_no_sensitive_keys(val, f"{path}.{key}" if path else str(key))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            _validate_no_sensitive_keys(item, path)


# ── Core Audit Log Model ──────────────────────────────────────────────────────

class AuditLogBase(BaseModel):
    """
    Representation of an immutable audit log record.
    Append-only and tamper-resistant document.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Audit event UUID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the audited action",
    )
    actor_id: str = Field(..., description="ID of the actor, or 'anonymous'")
    actor_role: str = Field(..., description="Role of the actor at time of action")
    action: AuditAction = Field(..., description="The specific audited action")
    target_type: Optional[str] = Field(default=None, description="Type of target resource (e.g. 'student', 'course')")
    target_id: Optional[str] = Field(default=None, description="Identifier of target (must be PID if target_type is student)")
    outcome: AuditOutcome = Field(default=AuditOutcome.SUCCESS, description="success, failed, or denied")
    reason: Optional[str] = Field(default=None, description="Mandatory justification reason for IDENTITY_REVEAL")
    ip_address: str = Field(..., description="Client IP address recorded via request tracking")
    user_agent: str = Field(..., description="Client user-agent string")
    request_id: str = Field(..., description="Correlation request ID matching X-Request-ID")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized metadata dictionary")
    schema_version: int = Field(default=1, description="Audit log schema version")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @model_validator(mode="after")
    def validate_audit_integrity(self) -> "AuditLogBase":
        # 1. Target ID must be a PID if target_type is 'student'
        if self.target_type and self.target_type.strip().lower() == "student":
            if not self.target_id:
                raise ValueError("target_id is required when target_type is 'student'.")
            if not str(self.target_id).startswith("STU_"):
                raise ValueError(
                    f"target_id must be a pseudonym ID (PID starting with 'STU_') when target_type is 'student'. Got '{self.target_id}'."
                )

        # 2. Reason is strictly required (min 10 chars) for IDENTITY_REVEAL
        if self.action == AuditAction.IDENTITY_REVEAL:
            if not self.reason or len(self.reason.strip()) < 10:
                raise ValueError(
                    "A valid justification reason of at least 10 characters is required for IDENTITY_REVEAL."
                )

        # 3. Details must not contain any sensitive keys from the denylist
        if self.details is not None:
            _validate_no_sensitive_keys(self.details)

        return self


# ── Query & Pagination Models ─────────────────────────────────────────────────

class AuditLogFilterParams(BaseModel):
    """Query filters for audit log queries."""
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    action: Optional[AuditAction] = None
    outcome: Optional[AuditOutcome] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class AuditLogQueryResponse(BaseModel):
    """Paginated response for audit log search."""
    items: List[AuditLogBase]
    total: int
    page: int
    limit: int
    pages: int

    model_config = {"from_attributes": True}
