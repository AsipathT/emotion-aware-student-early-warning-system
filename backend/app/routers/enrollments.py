"""
backend/app/routers/enrollments.py

Course enrollment endpoints (MongoDB backed - Feature 4 & Feature 21).
Reads and writes to canonical col.ENROLMENTS using pseudonym identifiers (PID).
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.db import collections as col
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
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> EnrollmentResponse:
    cid_str = str(course_id).strip()
    course_doc = (
        await db[col.COURSES].find_one({"_id": cid_str})
        or await db[col.COURSES].find_one({"id": cid_str})
        or await db[col.COURSES].find_one({"course_id": cid_str})
    )
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
    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    pid = (user_doc.get("pid") if user_doc else None) or getattr(current_user, "pid", None)
    if not pid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student profile has no pseudonym identifier (PID). Identity setup required before enrolling.",
        )

    existing = await db[col.ENROLMENTS].find_one({
        "pid": pid,
        "course_id": cid_str,
        "status": "active",
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
        "pid": pid,
        "course_id": cid_str,
        "enrolment_start": now,
        "status": "active",
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
    }

    await db[col.ENROLMENTS].insert_one(enr_doc)

    course_summary = EnrollmentCourseSummary(
        id=course_doc.get("id") or course_doc["_id"],
        title=course_doc["title"],
        description=course_doc.get("description"),
        lecturer_id=course_doc.get("lecturer_id"),
        is_published=course_doc.get("is_published", True),
        created_at=course_doc.get("created_at") or now,
    )
    student_summary = EnrollmentStudentSummary(
        id=user_doc.get("_id", uid_str) if user_doc else uid_str,
        email=user_doc.get("email", current_user.email) if user_doc else current_user.email,
        full_name=user_doc.get("full_name", current_user.full_name) if user_doc else current_user.full_name,
        role=user_doc.get("role", current_user.role) if user_doc else current_user.role,
        profile=user_doc.get("profile") if user_doc else None,
    )

    return EnrollmentResponse(
        id=eid,
        student_id=user_doc.get("_id", uid_str) if user_doc else uid_str,
        course_id=cid_str,
        status="active",
        enrolled_at=now,
        updated_at=now,
        course=course_summary,
        student=student_summary,
    )


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
    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    pid = (user_doc.get("pid") if user_doc else None) or getattr(current_user, "pid", None)
    if not pid:
        return []

    cursor = db[col.ENROLMENTS].find({"pid": pid}).sort("enrolment_start", -1)
    enrollments_docs = await cursor.to_list(length=1000)
    if not enrollments_docs:
        return []

    course_ids = list({e["course_id"] for e in enrollments_docs})
    courses_cursor = db[col.COURSES].find({
        "$or": [
            {"_id": {"$in": course_ids}},
            {"id": {"$in": course_ids}},
            {"course_id": {"$in": course_ids}},
        ]
    })
    course_docs = await courses_cursor.to_list(length=1000)
    course_map = {}
    for c in course_docs:
        course_map[str(c["_id"])] = c
        if c.get("id"):
            course_map[str(c["id"])] = c
        if c.get("course_id"):
            course_map[str(c["course_id"])] = c

    student_summary = EnrollmentStudentSummary(
        id=user_doc.get("_id", uid_str) if user_doc else uid_str,
        email=user_doc.get("email", current_user.email) if user_doc else current_user.email,
        full_name=user_doc.get("full_name", current_user.full_name) if user_doc else current_user.full_name,
        role=user_doc.get("role", current_user.role) if user_doc else current_user.role,
        profile=user_doc.get("profile") if user_doc else None,
    )

    results = []
    for enr in enrollments_docs:
        cid_str = enr["course_id"]
        c_doc = course_map.get(cid_str)
        c_summary = None
        if c_doc:
            c_summary = EnrollmentCourseSummary(
                id=c_doc.get("id") or c_doc["_id"],
                title=c_doc["title"],
                description=c_doc.get("description"),
                lecturer_id=c_doc.get("lecturer_id"),
                is_published=c_doc.get("is_published", True),
                created_at=c_doc.get("created_at") or datetime.now(timezone.utc),
            )
        enrolled_dt = enr.get("enrolment_start") or datetime.now(timezone.utc)
        results.append(
            EnrollmentResponse(
                id=str(enr["_id"]),
                student_id=user_doc.get("_id", uid_str) if user_doc else uid_str,
                course_id=cid_str,
                status=enr.get("status", "active"),
                enrolled_at=enrolled_dt,
                updated_at=enr.get("updated_at") or enrolled_dt,
                course=c_summary,
                student=student_summary,
            )
        )

    return results


# ── GET /api/v1/courses/{course_id}/enrollments ───────────────────────────────

@router.get(
    "/api/v1/courses/{course_id}/enrollments",
    response_model=List[EnrollmentResponse],
    summary="Get course student roster (Lecturer or Admin)",
    description="Returns the complete list of enrolled students for a given course from MongoDB.",
)
async def get_course_roster(
    course_id: str,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[EnrollmentResponse]:
    cid_str = str(course_id).strip()
    course_doc = (
        await db[col.COURSES].find_one({"_id": cid_str})
        or await db[col.COURSES].find_one({"id": cid_str})
        or await db[col.COURSES].find_one({"course_id": cid_str})
    )
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

    cursor = db[col.ENROLMENTS].find({"course_id": cid_str}).sort("enrolment_start", -1)
    roster_docs = await cursor.to_list(length=1000)

    course_summary = EnrollmentCourseSummary(
        id=course_doc.get("id") or course_doc["_id"],
        title=course_doc["title"],
        description=course_doc.get("description"),
        lecturer_id=course_doc.get("lecturer_id"),
        is_published=course_doc.get("is_published", True),
        created_at=course_doc.get("created_at") or datetime.now(timezone.utc),
    )

    # Batch query users for all PIDs in ONE single query
    pids = list({enr["pid"] for enr in roster_docs if enr.get("pid")})
    student_ids = list({enr["student_id"] for enr in roster_docs if enr.get("student_id")})
    user_map = {}
    if pids or student_ids:
        query_clauses = []
        if pids:
            query_clauses.append({"pid": {"$in": pids}})
        if student_ids:
            query_clauses.append({"_id": {"$in": student_ids}})
            query_clauses.append({"id": {"$in": student_ids}})
        users_cursor = db.users.find({"$or": query_clauses}) if len(query_clauses) > 1 else db.users.find(query_clauses[0])
        users_docs = await users_cursor.to_list(length=1000)
        for u in users_docs:
            if u.get("pid"):
                user_map[u["pid"]] = u
            user_map[str(u.get("_id"))] = u
            if u.get("id"):
                user_map[str(u.get("id"))] = u

    results = []
    for enr in roster_docs:
        pid = enr.get("pid")
        sid = enr.get("student_id")
        user_doc = user_map.get(pid) or (user_map.get(sid) if sid else None)
        student_summary = None
        student_id_val = str(user_doc["_id"]) if user_doc else (pid or sid)
        if user_doc:
            student_summary = EnrollmentStudentSummary(
                id=user_doc["_id"],
                email=user_doc.get("email", ""),
                full_name=user_doc.get("full_name", ""),
                role=user_doc.get("role", UserRole.STUDENT),
                profile=user_doc.get("profile"),
            )
        enrolled_dt = enr.get("enrolment_start") or datetime.now(timezone.utc)
        results.append(
            EnrollmentResponse(
                id=str(enr["_id"]),
                student_id=student_id_val,
                course_id=cid_str,
                status=enr.get("status", "active"),
                enrolled_at=enrolled_dt,
                updated_at=enr.get("updated_at") or enrolled_dt,
                course=course_summary,
                student=student_summary,
            )
        )

    return results
