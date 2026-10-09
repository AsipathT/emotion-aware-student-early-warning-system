"""
backend/app/routers/admin.py

Admin Panel endpoints (Feature 40).
All endpoints in this router strictly require the ADMIN role via get_current_admin.

Endpoints
---------
  GET  /api/v1/admin/stats               – System-wide metrics & resource counts
  GET  /api/v1/admin/users               – List all accounts and nested profiles
  PUT  /api/v1/admin/users/{id}/status   – Activate / suspend user account
  PUT  /api/v1/admin/users/{id}/role     – Promote / modify user authorization role
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_admin
from app.models.course import Course
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
    description="Returns aggregate counts of users, active accounts, roles, and courses.",
)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
) -> SystemStatsResponse:
    # Query users counts
    total_users_res = await db.execute(select(func.count(User.id)))
    total_users = total_users_res.scalar_one() or 0

    active_users_res = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    )
    active_users = active_users_res.scalar_one() or 0

    students_res = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.STUDENT)
    )
    total_students = students_res.scalar_one() or 0

    lecturers_res = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.LECTURER)
    )
    total_lecturers = lecturers_res.scalar_one() or 0

    # Query courses counts
    total_courses_res = await db.execute(select(func.count(Course.id)))
    total_courses = total_courses_res.scalar_one() or 0

    published_courses_res = await db.execute(
        select(func.count(Course.id)).where(Course.is_published == True)  # noqa: E712
    )
    published_courses = published_courses_res.scalar_one() or 0

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
    description="Returns all registered accounts with nested profile records.",
)
async def list_all_users(
    db: AsyncSession = Depends(get_db),
) -> List[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .order_by(User.created_at.desc())
        .execution_options(populate_existing=True)
    )
    users = result.scalars().all()
    return list(users)


# ── PUT /api/v1/admin/users/{user_id}/status ──────────────────────────────────

@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update user active/suspended status",
    description="Activates or suspends a specific user account.",
)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )

    # Prevent administrators from accidentally locking themselves out
    if user.id == current_admin.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own active account.",
        )

    user.is_active = body.is_active
    await db.flush()
    await db.refresh(user)
    return user


# ── PUT /api/v1/admin/users/{user_id}/role ────────────────────────────────────

@router.put(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Update user role",
    description="Assigns a new authorization role (Student, Lecturer, Counsellor, Admin) to a user.",
)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )

    # Prevent admin from removing their own admin status
    if user.id == current_admin.id and body.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account role.",
        )

    user.role = body.role
    await db.flush()
    await db.refresh(user)
    return user
