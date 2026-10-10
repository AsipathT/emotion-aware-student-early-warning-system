"""
backend/app/routers/auth.py

Authentication endpoints – register, login, and token refresh (MongoDB backed).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserResponse,
)

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
    description="Creates a new user account and stores document in MongoDB 'users' collection.",
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

    if not email or not password:
        raise _INVALID_CREDENTIALS

    user_doc = await db.users.find_one({"email": email})

    # Generic error message to prevent enumeration
    if not user_doc or not verify_password(password, user_doc.get("hashed_password", "")):
        raise _INVALID_CREDENTIALS

    if not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    user_id_str = str(user_doc["_id"])
    role_str = str(user_doc.get("role", "student"))

    return TokenResponse(
        access_token=create_access_token(user_id_str, role_str),
        refresh_token=create_refresh_token(user_id_str, role_str),
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

    return TokenResponse(
        access_token=create_access_token(user_id_str, role_str),
        refresh_token=create_refresh_token(user_id_str, role_str),
    )
