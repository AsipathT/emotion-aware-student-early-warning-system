"""
backend/app/routers/users.py

User profile management endpoints (MongoDB backed).
Integrates with Feature 5 Identity Vault for student pseudonymization sync.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.privacy import pseudonymize
from app.models.user import User, UserRole
from app.schemas.profile import ProfileResponse, ProfileUpdate, UserDetailResponse, UserMeResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ── GET /api/v1/users/me ──────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user's account and profile",
    description="Returns the authenticated user's full account details and their profile from MongoDB.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> UserMeResponse:
    user_doc = await db.users.find_one({"_id": str(current_user.id)})
    if not user_doc:
        user_doc = await db.users.find_one({"id": str(current_user.id)})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserMeResponse(**user_doc)


# ── PUT /api/v1/users/me/profile ──────────────────────────────────────────────

@router.put(
    "/me/profile",
    response_model=ProfileResponse,
    summary="Create or update the current user's profile",
    description="Upserts the user's profile embedded document in MongoDB and synchronizes with Identity Vault.",
)
async def upsert_my_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ProfileResponse:
    user_id = str(current_user.id)
    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        user_doc = await db.users.find_one({"id": user_id})

    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    now = datetime.now(timezone.utc)
    profile_dict = user_doc.get("profile") or {}

    if not profile_dict.get("id"):
        profile_dict["id"] = str(uuid.uuid4())
        profile_dict["created_at"] = now

    update_fields = body.model_dump(exclude_unset=True)
    profile_dict.update(update_fields)
    profile_dict["updated_at"] = now

    update_doc = {"profile": profile_dict, "updated_at": now}

    # Feature 5: If student updates their student_id, sync with identity_vault
    effective_student_id = profile_dict.get("student_id")
    if current_user.role == UserRole.STUDENT and effective_student_id:
        pid = pseudonymize(effective_student_id)
        update_doc["pid"] = pid
        update_doc["student_id"] = effective_student_id

        vault_doc = {
            "_id": pid,
            "pid": pid,
            "student_id": effective_student_id,
            "name": current_user.full_name,
            "email": current_user.email,
            "updated_at": now,
        }
        await db.identity_vault.update_one(
            {"pid": pid},
            {"$set": vault_doc},
            upsert=True,
        )

    await db.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": update_doc},
    )

    return ProfileResponse(**profile_dict)


# ── GET /api/v1/users/{user_id} ───────────────────────────────────────────────

@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get any user's details (Admin / Counsellor only)",
    description="Fetches the full account and profile for any user by UUID.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.COUNSELLOR))],
)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> UserDetailResponse:
    uid_str = str(user_id)
    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )
    return UserDetailResponse(**user_doc)
