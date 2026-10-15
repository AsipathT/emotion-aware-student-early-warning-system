"""
backend/app/routers/notifications.py

Feature 37: Student Notification Router (Component 4 Uptake Path).
Provides real-time in-app notification querying, badge counts, and read status management
for authenticated LMS users (students, counsellors, lecturers, admins).
"""

from datetime import datetime, timezone
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.notification import COL_NOTIFICATIONS
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationItem,
    NotificationListResponse,
    UnreadCountResponse,
)

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Get user notifications",
)
async def get_user_notifications(
    unread_only: bool = Query(default=False, description="Filter for unread notifications only"),
    page: int = Query(default=1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Retrieves chronologically sorted notifications for the current authenticated user.
    Restricted strictly to the user's own notification feed.
    """
    user_id = str(current_user.id)
    filter_query = {"user_id": user_id}
    if unread_only:
        filter_query["read_at"] = None

    total_count = await db[COL_NOTIFICATIONS].count_documents(filter_query)
    unread_count = await db[COL_NOTIFICATIONS].count_documents(
        {"user_id": user_id, "read_at": None}
    )

    skip = (page - 1) * page_size
    cursor = (
        db[COL_NOTIFICATIONS]
        .find(filter_query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        items.append(
            NotificationItem(
                id=doc["id"],
                user_id=doc["user_id"],
                type=doc["type"],
                title=doc["title"],
                body=doc["body"],
                link=doc.get("link"),
                related_id=doc.get("related_id"),
                created_at=doc["created_at"],
                read_at=doc.get("read_at"),
                is_read=doc.get("read_at") is not None,
            )
        )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return NotificationListResponse(
        items=items,
        total_count=total_count,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count badge",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns the real-time unread notification count for the active user badge.
    """
    user_id = str(current_user.id)
    count = await db[COL_NOTIFICATIONS].count_documents(
        {"user_id": user_id, "read_at": None}
    )
    return UnreadCountResponse(unread_count=count)


@router.post(
    "/{notification_id}/read",
    response_model=MarkReadResponse,
    summary="Mark single notification as read",
)
async def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Marks a designated notification as read.
    Enforces privacy boundary: returns HTTP 404 if notification belongs to another user or does not exist.
    """
    user_id = str(current_user.id)
    doc = await db[COL_NOTIFICATIONS].find_one(
        {"id": notification_id, "user_id": user_id}
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    now = datetime.now(timezone.utc)
    if doc.get("read_at") is None:
        await db[COL_NOTIFICATIONS].update_one(
            {"id": notification_id},
            {"$set": {"read_at": now}},
        )
        read_timestamp = now
    else:
        read_timestamp = doc["read_at"]

    return MarkReadResponse(id=notification_id, read_at=read_timestamp)


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark all user notifications as read",
)
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Bulk marks all unread notifications for the active user as read.
    """
    user_id = str(current_user.id)
    now = datetime.now(timezone.utc)
    result = await db[COL_NOTIFICATIONS].update_many(
        {"user_id": user_id, "read_at": None},
        {"$set": {"read_at": now}},
    )
    return MarkAllReadResponse(marked_count=result.modified_count)
