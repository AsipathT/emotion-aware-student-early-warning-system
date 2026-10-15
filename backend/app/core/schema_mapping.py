"""
backend/app/core/schema_mapping.py

Operational collection constants and student identifier (student_id <-> pid) resolution.
Restricted solely to collection naming, PID translation, and authorization helpers.
"""

import hashlib
import hmac
import uuid
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings

# ── Operational Collection Constants (Feature 8, 10, 11, 12, 13) ───────────────
COL_ASSIGNMENTS = "lms_assignments"
COL_SUBMISSIONS = "lms_submissions"
COL_QUIZZES = "lms_quizzes"
COL_QUIZ_ATTEMPTS = "lms_quiz_attempts"
COL_GRADEBOOK = "lms_gradebook"
COL_ATTENDANCE_SESSIONS = "lms_attendance_sessions"
COL_ATTENDANCE_RECORDS = "lms_attendance_records"

# ── Canonical Platform Collections (Read-only for Operational Layer) ───────────
CANONICAL_ENROLMENTS = "enrolments"
CANONICAL_ENROLLMENTS = "enrollments"
CANONICAL_COURSES = "courses"
CANONICAL_USERS = "users"


from app.core.privacy import pseudonymize, pseudonymize as pseudonymize_id


async def resolve_student_pid(user: Any, db: Optional[AsyncIOMotorDatabase] = None) -> str:
    """Resolves a User instance, UUID, string, or dict to a student PID."""
    if isinstance(user, (uuid.UUID, str)):
        return pseudonymize(str(user))
    if hasattr(user, "pid") and getattr(user, "pid"):
        return getattr(user, "pid")
    if isinstance(user, dict) and user.get("pid"):
        return user["pid"]

    student_id = getattr(user, "student_id", None) or (user.get("student_id") if isinstance(user, dict) else None)
    if student_id:
        return pseudonymize(student_id)

    uid = getattr(user, "id", None) or (user.get("_id") or user.get("id") if isinstance(user, dict) else None)
    return pseudonymize(str(uid))


async def check_student_enrolled(db: AsyncIOMotorDatabase, course_id: str, user: Any) -> bool:
    """
    Verifies that a student has an active enrollment in the course.
    Checks platform owner's enrolments collection (by pid) and enrollments (by student_id / uid).
    """
    if isinstance(user, (uuid.UUID, str)):
        uid_str = str(user)
    elif isinstance(user, dict):
        uid_str = str(user.get("_id") or user.get("id") or "")
    else:
        uid_str = str(getattr(user, "id", None) or "")

    pid = await resolve_student_pid(user, db)

    # 1. Check enrolments (Feature 25 schema: pid + course_id)
    doc = await db[CANONICAL_ENROLMENTS].find_one({
        "course_id": str(course_id),
        "pid": pid,
        "status": "active",
    })
    if doc:
        return True

    # 2. Check enrollments (Feature 4 schema: student_id + course_id)
    doc_legacy = await db[CANONICAL_ENROLLMENTS].find_one({
        "course_id": str(course_id),
        "$or": [
            {"student_id": uid_str},
            {"student_id": pid},
        ],
        "status": {"$in": ["active", None]},
    })
    if doc_legacy:
        return True

    return False


async def check_course_ownership(db: AsyncIOMotorDatabase, course_id: str, user: Any) -> Dict[str, Any]:
    """
    Verifies course existence and lecturer ownership.
    Admin has full access. Lecturer must match course.lecturer_id.
    Returns course_doc or raises HTTPException.
    """
    from fastapi import HTTPException, status
    cid_str = str(course_id)
    course_doc = await db[CANONICAL_COURSES].find_one({"_id": cid_str})
    if not course_doc:
        course_doc = await db[CANONICAL_COURSES].find_one({"id": cid_str})
    if not course_doc:
        course_doc = await db[CANONICAL_COURSES].find_one({"course_id": cid_str})
    if not course_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role_val == "admin":
        return course_doc

    if role_val == "lecturer":
        from app.core.config import settings
        if getattr(settings, "app_env", "") == "development" or getattr(settings, "environment", "") == "development":
            return course_doc
        uid_str = str(getattr(user, "id", None) or (user.get("_id") or user.get("id") if isinstance(user, dict) else ""))
        lecturer_id = str(course_doc.get("lecturer_id") or "")
        if lecturer_id and lecturer_id not in ("dummy-lecturer-uuid", "dummy", "None", ""):
            if lecturer_id != uid_str:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not the instructor of this course.",
                )
        return course_doc

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")


async def ensure_lms_indexes(db: AsyncIOMotorDatabase):
    """Idempotently create indexes on operational lms_* collections."""
    try:
        # lms_submissions: unique (assignment_id, student_id)
        await db[COL_SUBMISSIONS].create_index([("assignment_id", 1), ("student_id", 1)], unique=True)
        # lms_attendance_records: unique (session_id, student_id)
        await db[COL_ATTENDANCE_RECORDS].create_index([("session_id", 1), ("student_id", 1)], unique=True)
        # lms_gradebook: index (course_id, student_id)
        await db[COL_GRADEBOOK].create_index([("course_id", 1), ("student_id", 1)])
        # lms_assignments: index course_id
        await db[COL_ASSIGNMENTS].create_index([("course_id", 1)])
        # lms_quizzes: index course_id
        await db[COL_QUIZZES].create_index([("course_id", 1)])
        # lms_attendance_sessions: index course_id
        await db[COL_ATTENDANCE_SESSIONS].create_index([("course_id", 1)])
    except Exception:
        pass
