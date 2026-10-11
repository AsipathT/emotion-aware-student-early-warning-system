"""
backend/app/routers/auth.py

Authentication endpoints – register, login, and token refresh (MongoDB backed).
Integrated with Feature 5 Identity Vault for student pseudonymization.
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_db
from app.core.privacy import pseudonymize
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Shared exception ──────────────────────────────────────────────────────────
_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── POST /api/v1/auth/register ────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Creates a new user account. For students, writes pseudonymized records to identity_vault.",
)
async def register(
    body: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> UserResponse:
    # Duplicate e-mail guard
    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    role_val = body.role.value if hasattr(body.role, "value") else str(body.role)

    user_doc = {
        "_id": uid,
        "id": uid,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "full_name": body.full_name,
        "role": role_val,
        "is_active": True,
        "is_verified": False,
        "created_at": now,
        "updated_at": now,
        "profile": None,
    }

    # Feature 5: If role is student, generate deterministic PID and store in identity_vault
    if role_val == "student":
        student_id = body.student_id or f"IT{abs(hash(uid)) % 100000000:08d}"
        pid = pseudonymize(student_id)
        user_doc["student_id"] = student_id
        user_doc["pid"] = pid

        vault_doc = {
            "_id": pid,
            "pid": pid,
            "student_id": student_id,
            "name": body.full_name,
            "email": body.email,
            "created_at": now,
            "updated_at": now,
        }
        await db.identity_vault.update_one(
            {"pid": pid},
            {"$set": vault_doc},
            upsert=True,
        )

    await db.users.insert_one(user_doc)
    return UserResponse(**user_doc)


# ── POST /api/v1/auth/login ───────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain an access + refresh token pair",
    description="Validates email/password credentials against MongoDB and returns JWT tokens.",
)
async def login(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    content_type = request.headers.get("content-type", "").lower()
    email: str | None = None
    password: str | None = None

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        email = str(form.get("username") or form.get("email") or "")
        password = str(form.get("password") or "")
    else:
        try:
            body_json = await request.json()
            email = str(body_json.get("email") or body_json.get("username") or "")
            password = str(body_json.get("password") or "")
        except Exception:
            raise _INVALID_CREDENTIALS

    secret = settings.PSEUDONYM_SECRET_KEY.encode("utf-8")

    async def _log_failure(identifier: str) -> None:
        user_bytes = identifier.strip().lower().encode("utf-8")
        attempted_hmac = hmac.new(secret, user_bytes, hashlib.sha256).hexdigest()
        await log_event(
            request=request,
            db=db,
            action=AuditAction.LOGIN_FAILED,
            actor_id="anonymous",
            actor_role="anonymous",
            outcome=AuditOutcome.FAILED,
            details={"attempted_user_hmac": attempted_hmac},
        )

    if not email or not password:
        await _log_failure(email or "empty")
        raise _INVALID_CREDENTIALS

    user_doc = await db.users.find_one({"email": email})

    # Generic error message to prevent enumeration
    if not user_doc or not verify_password(password, user_doc.get("hashed_password", "")):
        await _log_failure(email)
        raise _INVALID_CREDENTIALS

    if not user_doc.get("is_active", True):
        await _log_failure(email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    user_id_str = str(user_doc["_id"])
    role_str = str(user_doc.get("role", "student"))

    # Feature 6: Check whether student must provide consent for active notice
    consent_required = False
    if role_str == "student":
        active_notice = await db.consent_notices.find_one({"is_active": True})
        if active_notice:
            pid = user_doc.get("pid")
            if not pid:
                student_id = user_doc.get("student_id") or user_id_str
                pid = pseudonymize(student_id)
                await db.users.update_one({"_id": user_doc["_id"]}, {"$set": {"pid": pid}})

            active_version = active_notice.get("version", 1)
            record = await db.consent_records.find_one({
                "pid": pid,
                "notice_version": active_version,
            })
            if not record:
                consent_required = True

    # Feature 7: Log successful login
    await log_event(
        request=request,
        db=db,
        action=AuditAction.LOGIN_SUCCESS,
        actor_id=user_id_str,
        actor_role=role_str,
        outcome=AuditOutcome.SUCCESS,
        details={"consent_required": consent_required},
    )

    return TokenResponse(
        access_token=create_access_token(user_id_str, role_str),
        refresh_token=create_refresh_token(user_id_str, role_str),
        consent_required=consent_required,
    )



# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Issue a new token pair from a valid refresh token",
)
async def refresh_tokens(
    body: TokenRefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    _bad_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise _bad_token

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise _bad_token

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _bad_token

    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        user_doc = await db.users.find_one({"id": user_id})

    if not user_doc or not user_doc.get("is_active", True):
        raise _bad_token

    user_id_str = str(user_doc["_id"])
    role_str = str(user_doc.get("role", "student"))

    consent_required = False
    if role_str == "student":
        active_notice = await db.consent_notices.find_one({"is_active": True})
        if active_notice:
            pid = user_doc.get("pid")
            if not pid:
                student_id = user_doc.get("student_id") or user_id_str
                pid = pseudonymize(student_id)
                await db.users.update_one({"_id": user_doc["_id"]}, {"$set": {"pid": pid}})

            active_version = active_notice.get("version", 1)
            record = await db.consent_records.find_one({
                "pid": pid,
                "notice_version": active_version,
            })
            if not record:
                consent_required = True

    return TokenResponse(
        access_token=create_access_token(user_id_str, role_str),
        refresh_token=create_refresh_token(user_id_str, role_str),
        consent_required=consent_required,
    )

