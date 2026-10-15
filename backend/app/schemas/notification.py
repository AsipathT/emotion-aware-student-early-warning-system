"""
backend/app/schemas/notification.py

Feature 37: Pydantic Schemas for Student Notifications.
Defines input/output representations for notification feeds, unread badges, and status mutations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class NotificationItem(BaseModel):
    """Notification response item."""
    id: str
    user_id: str
    type: str
    title: str
    body: str
    link: Optional[str] = None
    related_id: Optional[str] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    is_read: bool

    model_config = {
        "from_attributes": True,
    }


class NotificationListResponse(BaseModel):
    """Paginated list of user notifications."""
    items: List[NotificationItem]
    total_count: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class UnreadCountResponse(BaseModel):
    """Real-time badge unread count."""
    unread_count: int


class MarkReadResponse(BaseModel):
    """Response when a single notification is marked as read."""
    id: str
    read_at: datetime


class MarkAllReadResponse(BaseModel):
    """Response when all unread notifications are marked as read."""
    marked_count: int
