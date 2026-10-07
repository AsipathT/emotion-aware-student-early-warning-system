"""
backend/app/routers/auth.py

Authentication endpoints – register, login, and token refresh.

All routes are mounted under the prefix /api/v1/auth (see main.py).

Security notes
--------------
* On login failure we deliberately return the same generic message whether
  the email is unknown or the password is wrong, to prevent user-enumeration.
* The refresh endpoint validates the `type` claim so access tokens cannot be
  used as refresh tokens and vice-versa.
* Passwords are never logged or returned in any response body.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
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
    description=(
        "Creates a new user with the provided email, password, full name, and role. "
        "Returns the created user profile (no password hash)."
    ),
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Duplicate e-mail guard
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    # flush → assigns server-side defaults (UUID, timestamps) before commit
    await db.flush()
    await db.refresh(user)
    return user


# ── POST /api/v1/auth/login ───────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain an access + refresh token pair",
    description=(
        "Validates email/password credentials and returns a short-lived access "
        "token (default 30 min) and a long-lived refresh token (default 7 days)."
    ),
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    # Generic message for both "not found" and "wrong password" cases
    if user is None or not verify_password(body.password, user.hashed_password):
        raise _INVALID_CREDENTIALS

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
    )


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Issue a new token pair from a valid refresh token",
    description=(
        "Accepts a valid, unexpired refresh token and returns a brand-new "
        "access + refresh token pair (refresh-token rotation)."
    ),
)
async def refresh_tokens(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
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

    # Reject access tokens presented at the refresh endpoint
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise _bad_token

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _bad_token

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise _bad_token

    # Rotate: issue a completely new token pair
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
    )
