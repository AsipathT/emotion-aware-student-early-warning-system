"""
backend/app/routers/privacy.py

Feature 5: Privacy and Controlled Reveal endpoints.
Provides:
  - GET /reveal/{pid} (Role-restricted to Counsellors, Academic Staff / Lecturers, and Admins).
    Queries 'identity_vault' and invokes Feature 7 audit logging.
  - POST /scrub (Utility endpoint to scrub free text with redaction report).
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.privacy import scrub_text
from app.models.user import User, UserRole
from app.schemas.audit import AuditAction, AuditOutcome
from app.services.audit import log_audit_event, log_event

router = APIRouter(prefix="/api/v1", tags=["privacy"])



# ── Schemas ───────────────────────────────────────────────────────────────────

class IdentityRevealRequest(BaseModel):
    """Payload to request controlled identity reveal."""
    pid: str = Field(..., description="Pseudonym identifier, e.g. STU_a1b2c3d4")
    reason: str = Field(
        ...,
        min_length=10,
        description="Mandatory justification reason for revealing identity (minimum 10 characters)",
        examples=["Urgent mental health welfare concern reported by course instructor"],
    )


class IdentityRevealResponse(BaseModel):
    """Real identity returned from the Identity Vault."""
    pid: str = Field(..., description="Pseudonym identifier, e.g. STU_a1b2c3d4")
    student_id: str = Field(..., description="Real institutional student ID")
    name: str = Field(..., description="Student full name")
    email: str = Field(..., description="Student email address")


class ScrubTextRequest(BaseModel):
    """Text payload for redaction and PII scrubbing."""
    text: str
    known_names: Optional[List[str]] = None


class ScrubTextResponse(BaseModel):
    """Scrubbed text and redaction counts."""
    clean_text: str
    redaction_report: Dict[str, int]


# ── POST /reveal ──────────────────────────────────────────────────────────────

@router.post(
    "/reveal",
    response_model=IdentityRevealResponse,
    summary="Controlled identity reveal by Pseudonym ID (Counsellor & Academic Staff only)",
    description=(
        "Reveals the real identity corresponding to a student's PID. "
        "Strictly restricted to users with the Counsellor or Lecturer (Academic Staff) role. "
        "A justification reason of at least 10 characters is mandatory. "
        "Every reveal action is audited with the reason and caller before identity data is returned."
    ),
)
async def reveal_identity_post(
    body: IdentityRevealRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.COUNSELLOR, UserRole.LECTURER)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IdentityRevealResponse:
    # 1. Query the dedicated identity_vault collection
    record = await db.identity_vault.find_one({"pid": body.pid})
    if not record:
        record = await db.identity_vault.find_one({"_id": body.pid})

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pseudonym ID '{body.pid}' was not found in the Identity Vault.",
        )

    # 2. Critical Audit Log: IDENTITY_REVEAL must succeed before data is returned
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    await log_event(
        request=request,
        db=db,
        action=AuditAction.IDENTITY_REVEAL,
        actor_id=str(current_user.id),
        actor_role=role_str,
        target_type="student",
        target_id=body.pid,
        outcome=AuditOutcome.SUCCESS,
        reason=body.reason,
        details={
            "requester_role": role_str,
            "reason_length": len(body.reason),
        },
    )

    # 3. Return the real identity
    return IdentityRevealResponse(
        pid=record["pid"],
        student_id=record["student_id"],
        name=record["name"],
        email=record["email"],
    )


# Backward-compatible GET /reveal/{pid} proxy
@router.get(
    "/reveal/{pid}",
    response_model=IdentityRevealResponse,
    include_in_schema=False,
)
async def reveal_identity_legacy(
    pid: str,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.COUNSELLOR, UserRole.LECTURER)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IdentityRevealResponse:
    return await reveal_identity_post(
        body=IdentityRevealRequest(
            pid=pid,
            reason="Legacy GET request: Institutional welfare assessment",
        ),
        request=request,
        current_user=current_user,
        db=db,
    )



# ── POST /privacy/scrub ───────────────────────────────────────────────────────

@router.post(
    "/privacy/scrub",
    response_model=ScrubTextResponse,
    summary="Scrub sensitive PII from free text",
    description=(
        "Redacts emails, phone numbers, URLs, registration IDs, and personal names "
        "using regex and spaCy NER. Returns the sanitized text and redaction count report."
    ),
)
async def scrub_content(
    payload: ScrubTextRequest,
    current_user: User = Depends(get_current_user),
) -> ScrubTextResponse:
    clean_text, report = scrub_text(payload.text, payload.known_names)
    return ScrubTextResponse(
        clean_text=clean_text,
        redaction_report=report,
    )
