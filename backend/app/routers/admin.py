"""
backend/app/routers/admin.py

Admin Panel endpoints (MongoDB backed - Feature 40).
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminUserResponse,
    SystemStatsResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


# ── GET /api/v1/admin/stats ───────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get system-wide platform statistics",
    description="Returns aggregate counts from MongoDB users and courses collections.",
)
async def get_system_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SystemStatsResponse:
    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})
    total_students = await db.users.count_documents({"role": "student"})
    total_lecturers = await db.users.count_documents({"role": "lecturer"})

    total_courses = await db.courses.count_documents({})
    published_courses = await db.courses.count_documents({"is_published": True})

    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_courses=total_courses,
        published_courses=published_courses,
        total_students=total_students,
        total_lecturers=total_lecturers,
    )


# ── GET /api/v1/admin/users ───────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=List[AdminUserResponse],
    summary="List all platform users",
    description="Returns all registered accounts with nested profile records from MongoDB.",
)
async def list_all_users(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[AdminUserResponse]:
    cursor = db.users.find({}).sort("created_at", -1)
    users_docs = await cursor.to_list(length=1000)
    return [AdminUserResponse(**u) for u in users_docs]


# ── PUT /api/v1/admin/users/{user_id}/status ──────────────────────────────────

@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update user active/suspended status",
    description="Activates or suspends a specific user account in MongoDB.",
)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    uid_str = str(user_id)
    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )

    # Prevent administrators from locking themselves out
    if str(user_doc["_id"]) == str(current_admin.id) and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own active account.",
        )

    now = datetime.now(timezone.utc)
    updated_doc = await db.users.find_one_and_update(
        {"_id": user_doc["_id"]},
        {"$set": {"is_active": body.is_active, "updated_at": now}},
        return_document=True,
    )

    return AdminUserResponse(**updated_doc)


# ── PUT /api/v1/admin/users/{user_id}/role ────────────────────────────────────

@router.put(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Update user role",
    description="Assigns a new authorization role to a user in MongoDB.",
)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    uid_str = str(user_id)
    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )

    # Prevent admin from removing their own admin status
    role_val = body.role.value if hasattr(body.role, "value") else str(body.role)
    if str(user_doc["_id"]) == str(current_admin.id) and role_val != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account role.",
        )

    now = datetime.now(timezone.utc)
    updated_doc = await db.users.find_one_and_update(
        {"_id": user_doc["_id"]},
        {"$set": {"role": role_val, "updated_at": now}},
        return_document=True,
    )

    return AdminUserResponse(**updated_doc)
