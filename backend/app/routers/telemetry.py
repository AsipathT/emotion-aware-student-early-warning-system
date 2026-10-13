"""
backend/app/routers/telemetry.py

Feature 9 & 19: Student Activity & Clickstream Telemetry Endpoints.
Receives live video interactions and navigation events, storing them into col.ACTIVITY_EVENTS.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.contract_version import CONTRACT_VERSION
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.privacy import pseudonymize
from app.db import collections as col
from app.models.user import User

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


class TelemetryEventCreate(BaseModel):
    course_id: Optional[str] = Field(default="general")
    week_index: int = Field(default=1, ge=0)
    event_type: str = Field(..., min_length=1)  # e.g., 'VIDEO_PLAY', 'VIDEO_PAUSE', 'VIDEO_SEEK_FORWARD', 'PAGE_CLICK', 'PAGE_VIEW'
    event_payload: Optional[Dict[str, Any]] = None
    clicks: int = Field(default=1, ge=0)


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def log_activity_event(
    payload: TelemetryEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Records student clickstream or lecture video interaction event into col.ACTIVITY_EVENTS.
    Automatically assigns Feature 5 student pseudonym (Pid).
    """
    now = datetime.now(timezone.utc)
    student_ref = current_user.student_id or str(current_user.id)
    pid = getattr(current_user, "pid", None) or pseudonymize(student_ref)

    event_id = str(uuid.uuid4())
    event_doc = {
        "_id": event_id,
        "id": event_id,
        "schema_version": 1,
        "pid": pid,
        "course_id": payload.course_id or "general",
        "week_index": payload.week_index,
        "event_type": payload.event_type.lower(),
        "event_payload": payload.event_payload or {},
        "clicks": payload.clicks,
        "timestamp": now,
        "ingested_at": now,
        "source_version": CONTRACT_VERSION,
    }

    await db[col.ACTIVITY_EVENTS].insert_one(event_doc)
    return {
        "event_id": event_id,
        "status": "recorded",
        "timestamp": now.isoformat(),
    }


@router.get("/course/{course_id}/recent")
async def get_recent_course_events(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns recent activity events for the user in this course.
    """
    student_ref = current_user.student_id or str(current_user.id)
    pid = getattr(current_user, "pid", None) or pseudonymize(student_ref)

    cursor = db[col.ACTIVITY_EVENTS].find(
        {"course_id": course_id, "pid": pid},
        {"_id": 0},
    ).sort("timestamp", -1).limit(20)

    events = await cursor.to_list(length=20)
    return events


@router.get("/sessions")
async def get_my_session_history(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns recent login and session events for the current user.
    """
    student_ref = current_user.student_id or str(current_user.id)
    pid = getattr(current_user, "pid", None) or pseudonymize(student_ref)

    cursor = db[col.ACTIVITY_EVENTS].find(
        {"pid": pid, "event_type": "login"},
        {"_id": 0},
    ).sort("timestamp", -1).limit(15)

    sessions = await cursor.to_list(length=15)
    return sessions


@router.get("/my-activity")
async def get_my_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns recent activity clickstream and interaction events for current user.
    """
    student_ref = current_user.student_id or str(current_user.id)
    pid = getattr(current_user, "pid", None) or pseudonymize(student_ref)

    cursor = db[col.ACTIVITY_EVENTS].find(
        {"pid": pid},
        {"_id": 0},
    ).sort("timestamp", -1).limit(30)

    events = await cursor.to_list(length=30)
    return events

