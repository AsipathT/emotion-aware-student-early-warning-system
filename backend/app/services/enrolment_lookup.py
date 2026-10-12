"""
backend/app/services/enrolment_lookup.py

Centralised helper for verifying active course enrolment via PID (Feature 4 & Feature 21).
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import collections as col


async def has_active_enrolment(
    db: AsyncIOMotorDatabase,
    user_id: str,
    course_id: str,
) -> bool:
    """
    Check if a user has an active enrolment in a course.

    Looks up the user document by _id (falling back to id) to resolve their
    pseudonym identifier (PID), then queries the canonical ``col.ENROLMENTS``
    collection for an active enrolment record. Returns False if the user or
    their PID does not exist or if no active enrolment is found.
    """
    uid_str = str(user_id).strip()
    cid_str = str(course_id).strip()

    user_doc = await db.users.find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db.users.find_one({"id": uid_str})

    pid = user_doc.get("pid") if user_doc else None
    if not pid:
        return False

    enrolment = await db[col.ENROLMENTS].find_one({
        "pid": pid,
        "course_id": cid_str,
        "status": "active",
    })
    return enrolment is not None
