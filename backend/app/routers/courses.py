"""
backend/app/routers/courses.py

Course and Module management endpoints.

Endpoints
---------
  POST  /api/v1/courses                      – Create course (Lecturer / Admin)
  GET   /api/v1/courses                      – List published courses (Admin views all)
  GET   /api/v1/courses/{course_id}          – Get course with nested modules
  POST  /api/v1/courses/{course_id}/modules  – Add module to course (Lecturer / Admin)
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.course import Course, Module
from app.models.user import User, UserRole
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    ModuleCreate,
    ModuleResponse,
)

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


# ── POST /api/v1/courses ──────────────────────────────────────────────────────

@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course (Lecturer or Admin)",
    description=(
        "Creates a new course. Lecturers are automatically assigned as the course instructor. "
        "Administrators may explicitly assign another lecturer via `lecturer_id`."
    ),
)
async def create_course(
    body: CourseCreate,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Course:
    target_lecturer_id = current_user.id

    if current_user.role == UserRole.LECTURER:
        if body.lecturer_id and body.lecturer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturers can only create courses assigned to themselves.",
            )
    elif current_user.role == UserRole.ADMIN and body.lecturer_id:
        # Validate that specified lecturer exists and is active
        lecturer_res = await db.execute(
            select(User).where(User.id == body.lecturer_id)
        )
        assigned_user = lecturer_res.scalar_one_or_none()
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecturer with ID {body.lecturer_id} does not exist.",
            )
        if not assigned_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned lecturer account is deactivated.",
            )
        target_lecturer_id = body.lecturer_id

    new_course = Course(
        title=body.title,
        description=body.description,
        lecturer_id=target_lecturer_id,
        is_published=body.is_published,
    )
    db.add(new_course)
    await db.flush()
    await db.refresh(new_course)

    # Pre-populate empty modules list for schema serialisation
    new_course.modules = []
    return new_course


# ── GET /api/v1/courses ───────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[CourseResponse],
    summary="List courses",
    description=(
        "Returns all published courses. Administrators can see all courses (published and unpublished). "
        "Lecturers also see their own unpublished drafts."
    ),
)
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Course]:
    query = (
        select(Course)
        .options(selectinload(Course.modules))
        .order_by(Course.created_at.desc())
    )

    if current_user.role == UserRole.ADMIN:
        # Admin sees everything
        pass
    elif current_user.role == UserRole.LECTURER:
        # Lecturer sees published courses plus their own course drafts
        query = query.where(
            or_(
                Course.is_published == True,
                Course.lecturer_id == current_user.id,
            )
        )
    else:
        # Students and Counsellors see only published courses
        query = query.where(Course.is_published == True)

    result = await db.execute(query)
    courses = result.scalars().all()
    return list(courses)


# ── GET /api/v1/courses/{course_id} ───────────────────────────────────────────

@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Get course with modules",
    description=(
        "Fetches a single course with its complete ordered curriculum modules. "
        "Unpublished courses are only viewable by their instructor or administrators."
    ),
)
async def get_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    query = (
        select(Course)
        .options(selectinload(Course.modules))
        .where(Course.id == course_id)
    )
    result = await db.execute(query)
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # Visibility permission check for unpublished courses
    if not course.is_published:
        can_access = (
            current_user.role in (UserRole.ADMIN, UserRole.COUNSELLOR)
            or course.lecturer_id == current_user.id
        )
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found.",
            )

    return course


# ── POST /api/v1/courses/{course_id}/modules ──────────────────────────────────

@router.post(
    "/{course_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a module to a course (Lecturer or Admin)",
    description=(
        "Appends a learning module to an existing course. Only the assigned lecturer "
        "or an administrator may add modules."
    ),
)
async def add_module(
    course_id: uuid.UUID,
    body: ModuleCreate,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Module:
    # Verify course exists
    course_res = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_res.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # Authorization: check ownership if caller is a lecturer
    if current_user.role == UserRole.LECTURER and course.lecturer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned course instructor or an administrator can add modules.",
        )

    module = Module(
        course_id=course_id,
        title=body.title,
        content_payload=body.content_payload,
        sequence_order=body.sequence_order,
    )
    db.add(module)
    await db.flush()
    await db.refresh(module)
    return module
