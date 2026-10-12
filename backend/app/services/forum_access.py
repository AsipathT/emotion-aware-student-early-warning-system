"""
backend/app/services/forum_access.py

Centralised course-level access control for the discussion forum.

Every forum endpoint delegates permission checks here so the rules live
in exactly one place.  The two public helpers are:

- ``verify_forum_access``  – called with an explicit course_id.
- ``verify_forum_access_by_thread`` – resolves course_id from a thread doc.
"""

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import User, UserRole
from app.services.enrolment_lookup import has_active_enrolment


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _load_course(db: AsyncIOMotorDatabase, course_id: str) -> dict:
    """
    Fetch a course document by id (trying _id first, then id).
    Raises 404 if not found.
    """
    course = await db.courses.find_one({"_id": course_id})
    if not course:
        course = await db.courses.find_one({"id": course_id})
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )
    return course


async def _is_enrolled(db: AsyncIOMotorDatabase, student_id: str, course_id: str) -> bool:
    """Return True if the student has an active enrollment in the course."""
    return await has_active_enrolment(db, student_id, course_id)



# ── Public API ────────────────────────────────────────────────────────────────

async def verify_forum_access(
    db: AsyncIOMotorDatabase,
    course_id: str,
    user: User,
    *,
    write: bool = False,
) -> dict:
    """
    Check that *user* may access the forum for *course_id*.

    Parameters
    ----------
    write : bool
        ``True`` for create-thread / reply operations.
        ``False`` for read-only listing / viewing.

    Returns
    -------
    dict
        The course document (useful to the caller so it need not re-fetch).

    Raises
    ------
    HTTPException 404
        Course does not exist.
    HTTPException 403
        User does not have the required permission.
    HTTPException 403
        Counsellor attempts a write operation.
    """
    course = await _load_course(db, course_id)

    uid = str(user.id)

    if user.role == UserRole.ADMIN:
        # Admins always have full access.
        return course

    if user.role == UserRole.COUNSELLOR:
        if write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Counsellors have read-only access to the forum.",
            )
        # Read access is unrestricted for counsellors.
        return course

    if user.role == UserRole.LECTURER:
        if str(course.get("lecturer_id")) != uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access forums for courses you instruct.",
            )
        return course

    # Student
    if not await _is_enrolled(db, uid, course_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in this course to access its forum.",
        )
    return course


async def verify_forum_access_by_thread(
    db: AsyncIOMotorDatabase,
    thread_id: str,
    user: User,
    *,
    write: bool = False,
) -> tuple[dict, dict]:
    """
    Load the thread, resolve its course_id, then run ``verify_forum_access``.

    Returns
    -------
    tuple[dict, dict]
        (thread_doc, course_doc)
    """
    thread = await db.forum_threads.find_one({"_id": thread_id})
    if not thread:
        thread = await db.forum_threads.find_one({"id": thread_id})
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found.",
        )

    course = await verify_forum_access(
        db,
        thread["course_id"],
        user,
        write=write,
    )
    return thread, course
