"""
backend/app/routers/users.py

User profile management endpoints.

All routes require a valid Bearer access token (get_current_user dependency).
Role restrictions are enforced at the dependency level using require_roles.

Endpoints
---------
  GET  /api/v1/users/me              – Authenticated user's own account + profile
  PUT  /api/v1/users/me/profile      – Update (upsert) own profile
  GET  /api/v1/users/{user_id}       – Admin / Counsellor only: view any user
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.profile import Profile
from app.models.user import User, UserRole
from app.schemas.profile import ProfileResponse, ProfileUpdate, UserDetailResponse, UserMeResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ── Helper: load user + eagerly joined profile ────────────────────────────────

async def _get_user_with_profile(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> User | None:
    """
    Return a User ORM object with its `profile` relationship pre-loaded,
    or None if no such user exists.

    populate_existing=True is required because get_current_user (which runs
    first in the same request/session) already loaded the User into the
    SQLAlchemy identity map WITHOUT the profile relationship. Without this
    flag, SQLAlchemy returns the stale cached User and selectinload cannot
    overwrite the already-initialised (noload) profile attribute.
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


# ── GET /api/v1/users/me ──────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user's account and profile",
    description=(
        "Returns the authenticated user's full account details and their "
        "profile (or null if the profile has not been created yet)."
    ),
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Re-fetch with profile eagerly loaded so the relationship is available
    user = await _get_user_with_profile(current_user.id, db)
    if user is None:  # pragma: no cover – should never happen for a valid token
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


# ── PUT /api/v1/users/me/profile ──────────────────────────────────────────────

@router.put(
    "/me/profile",
    response_model=ProfileResponse,
    summary="Create or update the current user's profile",
    description=(
        "Upsert semantics: creates the profile if it does not exist yet, "
        "otherwise updates only the supplied fields. "
        "Omitted fields retain their current values; pass `null` to clear a field."
    ),
)
async def upsert_my_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    # Try to load existing profile
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile: Profile | None = result.scalar_one_or_none()

    if profile is None:
        # ── CREATE ────────────────────────────────────────────────────────────
        profile = Profile(
            user_id=current_user.id,
            **body.model_dump(exclude_unset=False),
        )
        db.add(profile)
    else:
        # ── UPDATE (partial) ──────────────────────────────────────────────────
        # Only update fields that were explicitly supplied in the request body.
        update_data = body.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return profile


# ── GET /api/v1/users/{user_id} ───────────────────────────────────────────────

@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get any user's details (Admin / Counsellor only)",
    description=(
        "Fetches the full account and profile for any user by UUID. "
        "Access is restricted to users with the Admin or Counsellor role."
    ),
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.COUNSELLOR))],
)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    # current_user is resolved by require_roles; injected here for audit logging later
    current_user: User = Depends(get_current_user),
) -> User:
    user = await _get_user_with_profile(user_id, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )
    return user
