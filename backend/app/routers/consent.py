"""
backend/app/routers/consent.py

Feature 6: Consent and Ethics Notice endpoints.
Provides:
  - GET  /api/v1/consent/notice         (Public/Auth: Fetch currently active notice)
  - GET  /api/v1/consent/me             (Student: Fetch current user's consent posture & history)
  - POST /api/v1/consent/me             (Student: Record 'accepted' or 'declined' decision with Feature 7 audit)
  - POST /api/v1/consent/me/withdraw    (Student: Record 'withdrawn' decision with Feature 7 audit)
  - POST /api/v1/consent/notices        (Admin only: Publish new notice version and archive old)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.privacy import pseudonymize
from app.models.user import User, UserRole
from app.schemas.consent import (
    ConsentDecision,
    ConsentDecisionRequest,
    ConsentNotice,
    ConsentNoticeCreate,
    ConsentRecord,
    ConsentStatusResponse,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


def _extract_client_info(request: Request) -> str:
    """Extracts client IP and User-Agent summary for audit logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "unknown"

    ua = request.headers.get("user-agent", "unknown")
    return f"{client_ip} | {ua[:80]}"


async def _get_or_create_student_pid(user: User, db: AsyncIOMotorDatabase) -> str:
    """Ensures a student has a deterministic pseudonym identifier."""
    user_doc = await db.users.find_one({"_id": str(user.id)})
    if not user_doc:
        user_doc = await db.users.find_one({"id": str(user.id)})

    pid = user_doc.get("pid") if user_doc else None
    if not pid:
        student_id = (
            user_doc.get("student_id")
            if user_doc
            else getattr(user, "student_id", None)
        ) or str(user.id)
        pid = pseudonymize(student_id)
        await db.users.update_one({"_id": str(user.id)}, {"$set": {"pid": pid}})

    return pid


# ── GET /api/v1/consent/notice ────────────────────────────────────────────────
@router.get(
    "/notice",
    response_model=ConsentNotice,
    summary="Get currently active consent notice",
    description="Returns the active ethics and data usage notice along with its version.",
)
async def get_active_notice(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConsentNotice:
    notice_doc = await db.consent_notices.find_one({"is_active": True})
    if not notice_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active consent notice found.",
        )
    return ConsentNotice(
        id=str(notice_doc.get("_id") or notice_doc.get("id")),
        version=notice_doc["version"],
        text=notice_doc["text"],
        effective_from=notice_doc.get("effective_from") or datetime.now(timezone.utc),
        is_active=notice_doc.get("is_active", True),
    )


# ── GET /api/v1/consent/me ────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=ConsentStatusResponse,
    summary="Get current user's consent posture and history",
    description="Returns whether the user has consented to the active notice version, their latest decision, and history.",
)
async def get_my_consent_status(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConsentStatusResponse:
    # 1. Fetch active notice
    active_notice_doc = await db.consent_notices.find_one({"is_active": True})
    active_notice: Optional[ConsentNotice] = None
    if active_notice_doc:
        active_notice = ConsentNotice(
            id=str(active_notice_doc.get("_id") or active_notice_doc.get("id")),
            version=active_notice_doc["version"],
            text=active_notice_doc["text"],
            effective_from=active_notice_doc.get("effective_from") or datetime.now(timezone.utc),
            is_active=active_notice_doc.get("is_active", True),
        )

    # If non-student (lecturer, admin, counsellor), consent is not required
    if current_user.role != UserRole.STUDENT:
        return ConsentStatusResponse(
            has_consented=True,
            latest_decision=ConsentDecision.ACCEPTED,
            notice_version=active_notice.version if active_notice else None,
            timestamp=None,
            consent_required=False,
            active_notice=active_notice,
            history=[],
        )

    # 2. Student logic: resolve PID and find consent records
    pid = await _get_or_create_student_pid(current_user, db)

    cursor = db.consent_records.find({"pid": pid}).sort("timestamp", -1)
    raw_records = await cursor.to_list(length=100)

    history = [
        ConsentRecord(
            id=str(r.get("_id") or r.get("id")),
            pid=r["pid"],
            notice_version=r["notice_version"],
            decision=ConsentDecision(r["decision"]),
            timestamp=r["timestamp"],
            ip_or_client=r.get("ip_or_client"),
        )
        for r in raw_records
    ]

    active_version = active_notice.version if active_notice else 1
    # Find latest decision specifically for active version
    active_version_records = [r for r in history if r.notice_version == active_version]

    if not active_version_records:
        # No decision recorded for this active notice version
        return ConsentStatusResponse(
            has_consented=False,
            latest_decision=None,
            notice_version=active_version,
            timestamp=None,
            consent_required=True,
            active_notice=active_notice,
            history=history,
        )

    latest_rec = active_version_records[0]
    has_consented = (latest_rec.decision == ConsentDecision.ACCEPTED)

    return ConsentStatusResponse(
        has_consented=has_consented,
        latest_decision=latest_rec.decision,
        notice_version=active_version,
        timestamp=latest_rec.timestamp,
        consent_required=False,  # They have a recorded decision
        active_notice=active_notice,
        history=history,
    )


# ── POST /api/v1/consent/me ───────────────────────────────────────────────────
@router.post(
    "/me",
    response_model=ConsentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record student's consent decision ('accepted' or 'declined')",
    description=(
        "Records the decision in the consent_records collection associated with the student's PID. "
        "Invokes Feature 7 audit logger to record the action with tamper-evident metadata."
    ),
)
async def record_consent_decision(
    body: ConsentDecisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConsentRecord:
    # 1. Fetch active notice version
    active_notice_doc = await db.consent_notices.find_one({"is_active": True})
    active_version = active_notice_doc.get("version", 1) if active_notice_doc else 1

    # 2. Resolve PID
    pid = await _get_or_create_student_pid(current_user, db)

    # 3. Form consent record
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    client_info = _extract_client_info(request)

    record_doc = {
        "_id": record_id,
        "id": record_id,
        "pid": pid,
        "notice_version": active_version,
        "decision": body.decision.value,
        "timestamp": now,
        "ip_or_client": client_info,
    }
    await db.consent_records.insert_one(record_doc)

    # 4. Feature 7: Audit Logging
    audit_action = (
        "CONSENT_ACCEPTED"
        if body.decision == ConsentDecision.ACCEPTED
        else "CONSENT_DECLINED"
    )
    await log_audit_event(
        db=db,
        action=audit_action,
        requester_id=str(current_user.id),
        target_pid=pid,
        details={
            "notice_version": active_version,
            "decision": body.decision.value,
            "ip_or_client": client_info,
            "user_email": current_user.email,
        },
    )

    return ConsentRecord(
        id=record_id,
        pid=pid,
        notice_version=active_version,
        decision=body.decision,
        timestamp=now,
        ip_or_client=client_info,
    )


# ── POST /api/v1/consent/me/withdraw ──────────────────────────────────────────
@router.post(
    "/me/withdraw",
    response_model=ConsentRecord,
    status_code=status.HTTP_200_OK,
    summary="Withdraw student consent",
    description=(
        "Records a 'withdrawn' decision in consent_records and emits an audit event. "
        "Allows student to stop ongoing affective analytics data collection at any time."
    ),
)
async def withdraw_consent(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConsentRecord:
    active_notice_doc = await db.consent_notices.find_one({"is_active": True})
    active_version = active_notice_doc.get("version", 1) if active_notice_doc else 1

    pid = await _get_or_create_student_pid(current_user, db)

    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    client_info = _extract_client_info(request)

    record_doc = {
        "_id": record_id,
        "id": record_id,
        "pid": pid,
        "notice_version": active_version,
        "decision": ConsentDecision.WITHDRAWN.value,
        "timestamp": now,
        "ip_or_client": client_info,
    }
    await db.consent_records.insert_one(record_doc)

    # Feature 7: Audit Logging
    await log_audit_event(
        db=db,
        action="CONSENT_WITHDRAWN",
        requester_id=str(current_user.id),
        target_pid=pid,
        details={
            "notice_version": active_version,
            "decision": "withdrawn",
            "ip_or_client": client_info,
            "user_email": current_user.email,
        },
    )

    return ConsentRecord(
        id=record_id,
        pid=pid,
        notice_version=active_version,
        decision=ConsentDecision.WITHDRAWN,
        timestamp=now,
        ip_or_client=client_info,
    )


# ── POST /api/v1/consent/notices ──────────────────────────────────────────────
@router.post(
    "/notices",
    response_model=ConsentNotice,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new consent notice version (Admin only)",
    description=(
        "Archives the currently active notice by marking it inactive, creates a new active version "
        "with an incremented version number, and records the change in the Feature 7 audit log."
    ),
)
async def publish_new_notice(
    body: ConsentNoticeCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConsentNotice:
    # 1. Determine next version number
    highest_notice = await db.consent_notices.find_one(sort=[("version", -1)])
    next_version = (highest_notice.get("version", 0) + 1) if highest_notice else 1

    # 2. Deactivate existing notices
    await db.consent_notices.update_many({"is_active": True}, {"$set": {"is_active": False}})

    # 3. Create and insert new notice
    notice_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    notice_doc = {
        "_id": notice_id,
        "id": notice_id,
        "version": next_version,
        "text": body.text.strip(),
        "effective_from": now,
        "is_active": True,
    }
    await db.consent_notices.insert_one(notice_doc)

    # 4. Feature 7: Audit Logging
    await log_audit_event(
        db=db,
        action="NOTICE_PUBLISHED",
        requester_id=str(current_user.id),
        details={
            "new_version": next_version,
            "admin_email": current_user.email,
            "notice_length": len(body.text),
        },
    )

    return ConsentNotice(
        id=notice_id,
        version=next_version,
        text=notice_doc["text"],
        effective_from=now,
        is_active=True,
    )
