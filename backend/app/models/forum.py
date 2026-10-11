"""
backend/app/models/forum.py

MongoDB document models for the discussion forum (Feature 14).

Collections
-----------
- **forum_threads** – top-level discussion topics within a course.
- **forum_posts** – replies to a thread (flat list with parent_post_id
  for tree reconstruction on the frontend).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ForumThread(BaseModel):
    """Document stored in the ``forum_threads`` collection."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: str
    author_id: str
    author_role: str
    title: str
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reply_count: int = 0
    is_pinned: bool = False
    is_locked: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True, "populate_by_name": True}

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        tid = str(self.id)
        return {
            "_id": tid,
            "id": tid,
            "course_id": self.course_id,
            "author_id": self.author_id,
            "author_role": self.author_role,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_activity_at": self.last_activity_at,
            "reply_count": self.reply_count,
            "is_pinned": self.is_pinned,
            "is_locked": self.is_locked,
            "metadata": self.metadata,
        }


class ForumPost(BaseModel):
    """Document stored in the ``forum_posts`` collection."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    thread_id: str
    course_id: str
    author_id: str
    author_role: str
    parent_post_id: Optional[str] = None
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True, "populate_by_name": True}

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        pid = str(self.id)
        return {
            "_id": pid,
            "id": pid,
            "thread_id": self.thread_id,
            "course_id": self.course_id,
            "author_id": self.author_id,
            "author_role": self.author_role,
            "parent_post_id": self.parent_post_id,
            "body": self.body,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
