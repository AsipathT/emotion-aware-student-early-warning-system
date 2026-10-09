"""
backend/app/routers/enrollments.py

Course enrollment endpoints (MongoDB backed - Feature 4).
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.enrollment import (
    EnrollmentCourseSummary,
    EnrollmentResponse,
    EnrollmentStudentSummary,
)

router = APIRouter(tags=["enrollments"])


# ── POST /api/v1/enrollments/{course_id} ──────────────────────────────────────

@router.post(
    "/api/v1/enrollments/{course_id}",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a published course",
    description="Enrolls the authenticated student in the specified course in MongoDB.",
)
async def enroll_in_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> EnrollmentResponse:
    cid_str = str(course_id)
    course_doc = await db.courses.find_one({"_id": cid_str})
    if not course_doc:
        course_doc = await db.courses.find_one({"id": cid_str})

    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if not course_doc.get("is_published", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll in an unpublished course.",
        )

    uid_str = str(current_user.id)
    existing = await db.enrollments.find_one({
        "student_id": uid_str,
        "course_id": cid_str,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already enrolled in this course.",
        )

    eid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    enr_doc = {
        "_id": eid,
        "id": eid,
        "student_id": uid_str,
        "course_id": cid_str,
        "status": "active",
        "enrolled_at": now,
        "updated_at": now,
    }

    await db.enrollments.insert_one(enr_doc)

    # Attach nested course & student representations for schema
    user_doc = await db.users.find_one({"_id": uid_str}) or await db.users.find_one({"id": uid_str})
    enr_doc["course"] = EnrollmentCourseSummary(
        id=course_doc["_id"],
        title=course_doc["title"],
        description=course_doc.get("description"),
        lecturer_id=course_doc["lecturer_id"],
        is_published=course_doc["is_published"],
        created_at=course_doc["created_at"],
    )
    enr_doc["student"] = EnrollmentStudentSummary(
        id=user_doc["_id"],
        email=user_doc["email"],
        full_name=user_doc["full_name"],
        role=user_doc["role"],
        profile=user_doc.get("profile"),
    )

    return EnrollmentResponse(**enr_doc)


# ── GET /api/v1/enrollments/me ────────────────────────────────────────────────

@router.get(
    "/api/v1/enrollments/me",
    response_model=List[EnrollmentResponse],
    summary="List current student's enrollments",
    description="Returns all course enrollments for the calling student.",
)
async def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[EnrollmentResponse]:
    uid_str = str(current_user.id)
    cursor = db.enrollments.find({"student_id": uid_str}).sort("enrolled_at", -1)
    enrollments_docs = await cursor.to_list(length=1000)

    results = []
    for enr in enrollments_docs:
        cid_str = enr["course_id"]
        course_doc = await db.courses.find_one({"_id": cid_str}) or await db.courses.find_one({"id": cid_str})
        if course_doc:
            enr["course"] = EnrollmentCourseSummary(
                id=course_doc["_id"],
                title=course_doc["title"],
                description=course_doc.get("description"),
                lecturer_id=course_doc["lecturer_id"],
                is_published=course_doc["is_published"],
                created_at=course_doc["created_at"],
            )
        results.append(EnrollmentResponse(**enr))

    return results


# ── GET /api/v1/courses/{course_id}/enrollments ───────────────────────────────

@router.get(
    "/api/v1/courses/{course_id}/enrollments",
    response_model=List[EnrollmentResponse],
    summary="Get course student roster (Lecturer or Admin)",
    description="Returns the complete list of enrolled students for a given course from MongoDB.",
)
async def get_course_roster(
    course_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[EnrollmentResponse]:
    cid_str = str(course_id)
    course_doc = await db.courses.find_one({"_id": cid_str}) or await db.courses.find_one({"id": cid_str})
    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if current_user.role == UserRole.LECTURER and str(course_doc.get("lecturer_id")) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access student rosters for courses you instruct.",
        )

    cursor = db.enrollments.find({"course_id": cid_str}).sort("enrolled_at", -1)
    roster_docs = await cursor.to_list(length=1000)

    course_summary = EnrollmentCourseSummary(
        id=course_doc["_id"],
        title=course_doc["title"],
        description=course_doc.get("description"),
        lecturer_id=course_doc["lecturer_id"],
        is_published=course_doc["is_published"],
        created_at=course_doc["created_at"],
    )

    results = []
    for enr in roster_docs:
        enr["course"] = course_summary
        user_doc = await db.users.find_one({"_id": enr["student_id"]}) or await db.users.find_one({"id": enr["student_id"]})
        if user_doc:
            enr["student"] = EnrollmentStudentSummary(
                id=user_doc["_id"],
                email=user_doc["email"],
                full_name=user_doc["full_name"],
                role=user_doc["role"],
                profile=user_doc.get("profile"),
            )
        results.append(EnrollmentResponse(**enr))

    return results
