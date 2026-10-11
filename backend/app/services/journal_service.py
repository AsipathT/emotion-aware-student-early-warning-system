"""
backend/app/services/journal_service.py

Business logic and access control helpers for the Reflective Learning Journal (Feature 16).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import User, UserRole
from app.services.enrolment_lookup import has_active_enrolment


def require_student_role(user: User) -> None:
    """
    Ensure the user is a student.

    Lecturers, counsellors, admins, and all other non-student roles are denied
    access (403 Forbidden) to maintain strict privacy for student reflective text.
    """
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students may access the reflective journal.",
        )


def compute_current_week_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Calculate the calendar week boundaries (Monday 00:00:00 UTC to next Monday 00:00:00 UTC)
    for the given timestamp or current UTC time.

    Returns
    -------
    Tuple[datetime, datetime]
        (week_start, week_end) where both are UTC-aware datetimes.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Monday is weekday 0 in Python
    monday = now - timedelta(days=now.weekday())
    week_start = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


async def verify_active_enrolment(
    db: AsyncIOMotorDatabase,
    student_id: str,
    course_id: str,
) -> dict:
    """
    Verify that the course exists and that the student has an active enrolment.

    Returns
    -------
    dict
        The course document.

    Raises
    ------
    HTTPException 404
        If the course does not exist.
    HTTPException 403
        If the student is not actively enrolled in the course.
    """
    course = await db.courses.find_one({"_id": course_id})
    if not course:
        course = await db.courses.find_one({"id": course_id})
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if not await has_active_enrolment(db, student_id, course_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active enrolment in this course is required to access the journal.",
        )

    return course
