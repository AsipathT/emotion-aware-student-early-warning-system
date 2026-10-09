"""
backend/app/routers/courses.py

Course and Module management endpoints (MongoDB backed).
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
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
    description="Creates a course document and stores it in MongoDB 'courses' collection.",
)
async def create_course(
    body: CourseCreate,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CourseResponse:
    target_lecturer_id = current_user.id

    if current_user.role == UserRole.LECTURER:
        if body.lecturer_id and str(body.lecturer_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturers can only create courses assigned to themselves.",
            )
    elif current_user.role == UserRole.ADMIN and body.lecturer_id:
        target_str = str(body.lecturer_id)
        assigned_user = await db.users.find_one({"_id": target_str})
        if not assigned_user:
            assigned_user = await db.users.find_one({"id": target_str})
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecturer with ID {body.lecturer_id} does not exist.",
            )
        if not assigned_user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned lecturer account is deactivated.",
            )
        target_lecturer_id = body.lecturer_id

    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    course_doc = {
        "_id": cid,
        "id": cid,
        "title": body.title,
        "description": body.description,
        "lecturer_id": str(target_lecturer_id),
        "is_published": body.is_published,
        "created_at": now,
        "updated_at": now,
        "modules": [],
    }

    await db.courses.insert_one(course_doc)
    return CourseResponse(**course_doc)


# ── GET /api/v1/courses ───────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[CourseResponse],
    summary="List courses",
    description="Returns courses from MongoDB according to user role permissions.",
)
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[CourseResponse]:
    filter_q = {}

    if current_user.role == UserRole.ADMIN:
        filter_q = {}
    elif current_user.role == UserRole.LECTURER:
        filter_q = {
            "$or": [
                {"is_published": True},
                {"lecturer_id": str(current_user.id)},
            ]
        }
    else:
        filter_q = {"is_published": True}

    cursor = db.courses.find(filter_q).sort("created_at", -1)
    courses_docs = await cursor.to_list(length=1000)

    # Ensure modules are sorted by sequence_order in each course
    for c in courses_docs:
        c["modules"] = sorted(
            c.get("modules", []),
            key=lambda m: m.get("sequence_order", 1),
        )

    return [CourseResponse(**c) for c in courses_docs]


# ── GET /api/v1/courses/{course_id} ───────────────────────────────────────────

@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Get course with modules",
    description="Fetches a course and its embedded modules from MongoDB.",
)
async def get_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CourseResponse:
    cid_str = str(course_id)
    course_doc = await db.courses.find_one({"_id": cid_str})
    if not course_doc:
        course_doc = await db.courses.find_one({"id": cid_str})

    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # Visibility permission check for unpublished drafts
    if not course_doc.get("is_published", False):
        can_access = (
            current_user.role in (UserRole.ADMIN, UserRole.COUNSELLOR)
            or str(course_doc.get("lecturer_id")) == str(current_user.id)
        )
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found.",
            )

    course_doc["modules"] = sorted(
        course_doc.get("modules", []),
        key=lambda m: m.get("sequence_order", 1),
    )

    return CourseResponse(**course_doc)


# ── POST /api/v1/courses/{course_id}/modules ──────────────────────────────────

@router.post(
    "/{course_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a module to a course (Lecturer or Admin)",
    description="Pushes a new module into the course's modules array in MongoDB.",
)
async def add_module(
    course_id: uuid.UUID,
    body: ModuleCreate,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ModuleResponse:
    cid_str = str(course_id)
    course_doc = await db.courses.find_one({"_id": cid_str})
    if not course_doc:
        course_doc = await db.courses.find_one({"id": cid_str})

    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if current_user.role == UserRole.LECTURER and str(course_doc.get("lecturer_id")) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned course instructor or an administrator can add modules.",
        )

    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    module_doc = {
        "_id": mid,
        "id": mid,
        "course_id": cid_str,
        "title": body.title,
        "content_payload": body.content_payload,
        "sequence_order": body.sequence_order,
        "created_at": now,
        "updated_at": now,
    }

    await db.courses.update_one(
        {"_id": course_doc["_id"]},
        {
            "$push": {"modules": module_doc},
            "$set": {"updated_at": now},
        },
    )

    return ModuleResponse(**module_doc)
