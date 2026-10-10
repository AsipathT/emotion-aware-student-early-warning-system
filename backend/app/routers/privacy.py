"""
backend/app/routers/privacy.py

Feature 5: Privacy and Controlled Reveal endpoints.
Provides:
  - GET /reveal/{pid} (Role-restricted to Counsellors, Academic Staff / Lecturers, and Admins).
    Queries 'identity_vault' and invokes Feature 7 audit logging.
  - POST /scrub (Utility endpoint to scrub free text with redaction report).
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.privacy import scrub_text
from app.models.user import User, UserRole
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/v1", tags=["privacy"])


# ── Schemas ───────────────────────────────────────────────────────────────────

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


# ── GET /reveal/{pid} ─────────────────────────────────────────────────────────

@router.get(
    "/reveal/{pid}",
    response_model=IdentityRevealResponse,
    summary="Controlled identity reveal by Pseudonym ID (PID)",
    description=(
        "Reveals the real identity corresponding to a student's PID. "
        "Strictly restricted to users with the Counsellor, Lecturer (Academic Staff), or Admin roles. "
        "Every access attempt is recorded by the Feature 7 audit logging system."
    ),
)
async def reveal_identity(
    pid: str,
    current_user: User = Depends(require_roles(UserRole.COUNSELLOR, UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IdentityRevealResponse:
    # 1. Query the dedicated identity_vault collection
    record = await db.identity_vault.find_one({"pid": pid})
    if not record:
        record = await db.identity_vault.find_one({"_id": pid})

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pseudonym ID '{pid}' was not found in the Identity Vault.",
        )

    # 2. Invoke Feature 7 Audit Logging
    requester_role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    await log_audit_event(
        db=db,
        action="IDENTITY_REVEAL",
        requester_id=str(current_user.id),
        target_pid=pid,
        details={
            "requester_email": current_user.email,
            "requester_role": requester_role_str,
            "revealed_student_id": record.get("student_id"),
        },
    )

    # 3. Return the real identity
    return IdentityRevealResponse(
        pid=record["pid"],
        student_id=record["student_id"],
        name=record["name"],
        email=record["email"],
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
