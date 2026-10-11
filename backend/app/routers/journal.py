"""
backend/app/routers/journal.py

Reflective learning journal endpoints (Feature 16).

Prefix: /api/v1/journal
Tags:   ["journal"]
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.journal import (
    JournalCurrentResponse,
    JournalEntryCreate,
    JournalEntryResponse,
)
from app.services.communication_metadata import compute_text_stats
from app.services.journal_service import (
    compute_current_week_bounds,
    require_student_role,
    verify_active_enrolment,
)

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


# ── GET /courses/{course_id}/current ──────────────────────────────────────────

@router.get(
    "/courses/{course_id}/current",
    response_model=JournalCurrentResponse,
    summary="Get current week journal status for a course",
    description="Returns calendar week boundaries and whether the student has already submitted for this week.",
)
async def get_current_week_status(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> JournalCurrentResponse:
    require_student_role(current_user)

    uid = str(current_user.id)
    await verify_active_enrolment(db, uid, course_id)

    week_start, week_end = compute_current_week_bounds()

    entry = await db.journal_entries.find_one({
        "author_id": uid,
        "course_id": course_id,
        "week_start": week_start,
    })

    return JournalCurrentResponse(
        course_id=course_id,
        week_start=week_start,
        week_end=week_end,
        submitted=entry is not None,
        entry_id=str(entry["_id"]) if entry else None,
    )


# ── POST /entries ─────────────────────────────────────────────────────────────

@router.post(
    "/entries",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a weekly reflective journal entry",
    description="Submits an immutable journal entry for the current UTC calendar week. Enforces one entry per week.",
)
async def create_journal_entry(
    payload: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> JournalEntryResponse:
    require_student_role(current_user)

    uid = str(current_user.id)
    await verify_active_enrolment(db, uid, payload.course_id)

    week_start, _ = compute_current_week_bounds()
    now = datetime.now(timezone.utc)
    seconds_since_week_start = max(0.0, (now - week_start).total_seconds())

    stats = compute_text_stats(payload.body)
    metadata = {
        **stats,
        "seconds_since_week_start": seconds_since_week_start,
    }

    entry_id = str(uuid.uuid4())
    doc = {
        "_id": entry_id,
        "id": entry_id,
        "author_id": uid,
        "author_role": "student",
        "course_id": payload.course_id,
        "source_type": "journal",
        "week_start": week_start,
        "body": payload.body,
        "created_at": now,
        "metadata": metadata,
    }

    try:
        await db.journal_entries.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a journal entry for this course this week.",
        )

    return JournalEntryResponse(**doc)


# ── GET /entries ──────────────────────────────────────────────────────────────

@router.get(
    "/entries",
    response_model=List[JournalEntryResponse],
    summary="List student's reflective journal entries",
    description="Returns the calling student's past journal entries, ordered newest week first. Optionally filtered by course_id.",
)
async def list_journal_entries(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[JournalEntryResponse]:
    require_student_role(current_user)

    uid = str(current_user.id)
    query: dict = {"author_id": uid}
    if course_id:
        query["course_id"] = course_id

    cursor = (
        db.journal_entries
        .find(query)
        .sort([("week_start", -1), ("created_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [JournalEntryResponse(**d) for d in docs]


# ── GET /entries/{entry_id} ───────────────────────────────────────────────────

@router.get(
    "/entries/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get a single reflective journal entry",
    description="Fetches a specific journal entry. Returns 404 if not found or if authored by another user.",
)
async def get_journal_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> JournalEntryResponse:
    require_student_role(current_user)

    uid = str(current_user.id)
    entry = await db.journal_entries.find_one({"_id": entry_id})
    if not entry:
        entry = await db.journal_entries.find_one({"id": entry_id})

    # Do not reveal existence if not found or owned by someone else
    if not entry or entry.get("author_id") != uid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found.",
        )

    return JournalEntryResponse(**entry)
