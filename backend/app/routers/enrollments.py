"""
backend/app/routers/enrollments.py

Course enrollment endpoints (Feature 4).

Endpoints
---------
  POST  /api/v1/enrollments/{course_id}          – Student enrolls in published course
  GET   /api/v1/enrollments/me                   – Current student's active enrollments
  GET   /api/v1/courses/{course_id}/enrollments  – Course roster (Lecturer/Admin)
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentResponse

router = APIRouter(tags=["enrollments"])


# ── POST /api/v1/enrollments/{course_id} ──────────────────────────────────────

@router.post(
    "/api/v1/enrollments/{course_id}",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a published course",
    description=(
        "Enrolls the authenticated student in the specified course. "
        "Fails if the course is unpublished or if an enrollment already exists."
    ),
)
async def enroll_in_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Enrollment:
    # 1. Verify course exists
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # 2. Verify course is published
    if not course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll in an unpublished course.",
        )

    # 3. Prevent duplicate enrollment
    existing_res = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == course_id,
        )
    )
    if existing_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already enrolled in this course.",
        )

    # 4. Create new enrollment
    enrollment = Enrollment(
        student_id=current_user.id,
        course_id=course_id,
        status="active",
    )
    db.add(enrollment)
    await db.flush()
    await db.refresh(enrollment)

    # Attach loaded course & student objects for response schema serialisation
    enrollment.course = course
    enrollment.student = current_user
    return enrollment


# ── GET /api/v1/enrollments/me ────────────────────────────────────────────────

@router.get(
    "/api/v1/enrollments/me",
    response_model=List[EnrollmentResponse],
    summary="List current student's enrollments",
    description="Returns all course enrollments and course summaries for the calling student.",
)
async def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Enrollment]:
    result = await db.execute(
        select(Enrollment)
        .options(
            selectinload(Enrollment.course),
        )
        .where(Enrollment.student_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    enrollments = result.scalars().all()
    return list(enrollments)


# ── GET /api/v1/courses/{course_id}/enrollments ───────────────────────────────

@router.get(
    "/api/v1/courses/{course_id}/enrollments",
    response_model=List[EnrollmentResponse],
    summary="Get course student roster (Lecturer or Admin)",
    description=(
        "Returns the complete list of enrolled students for a given course. "
        "Lecturers may only access courses they instruct; administrators may view any roster."
    ),
)
async def get_course_roster(
    course_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[Enrollment]:
    # 1. Verify course exists
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # 2. If lecturer, verify ownership
    if current_user.role == UserRole.LECTURER and course.lecturer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access student rosters for courses you instruct.",
        )

    # 3. Fetch enrollments with student accounts and profiles
    result = await db.execute(
        select(Enrollment)
        .options(
            selectinload(Enrollment.student).selectinload(User.profile),
            selectinload(Enrollment.course),
        )
        .where(Enrollment.course_id == course_id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    roster = result.scalars().all()
    return list(roster)
