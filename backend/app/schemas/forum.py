"""
backend/app/schemas/forum.py

Pydantic v2 request / response schemas for the discussion forum (Feature 14).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Nested author summary (never exposes sensitive fields) ────────────────────

class AuthorSummary(BaseModel):
    """Lightweight user representation embedded in thread / post responses."""

    id: uuid.UUID
    full_name: str
    role: str

    model_config = {"from_attributes": True}


# ── Thread schemas ────────────────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    """Payload sent by the client when creating a new thread."""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)


class ThreadModerationUpdate(BaseModel):
    """Payload for pin / lock operations (lecturer-of-course or admin)."""

    is_pinned: Optional[bool] = None
    is_locked: Optional[bool] = None


class ThreadListItem(BaseModel):
    """Single item returned in the thread listing endpoint."""

    id: uuid.UUID
    course_id: str
    author_id: str
    author_role: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    reply_count: int
    is_pinned: bool
    is_locked: bool
    metadata: Dict[str, Any] = {}
    author: Optional[AuthorSummary] = None

    model_config = {"from_attributes": True}


class ThreadDetail(BaseModel):
    """Full thread returned by the single-thread detail endpoint."""

    id: uuid.UUID
    course_id: str
    author_id: str
    author_role: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    reply_count: int
    is_pinned: bool
    is_locked: bool
    metadata: Dict[str, Any] = {}
    author: Optional[AuthorSummary] = None
    posts: List["PostResponse"] = []

    model_config = {"from_attributes": True}


# ── Post schemas ──────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    """Payload sent by the client when replying to a thread."""

    body: str = Field(..., min_length=1, max_length=5000)
    parent_post_id: Optional[str] = None


class PostResponse(BaseModel):
    """Single post returned inside a thread detail or after creation."""

    id: uuid.UUID
    thread_id: str
    course_id: str
    author_id: str
    author_role: str
    parent_post_id: Optional[str] = None
    body: str
    created_at: datetime
    metadata: Dict[str, Any] = {}
    author: Optional[AuthorSummary] = None

    model_config = {"from_attributes": True}


# Rebuild forward refs so ThreadDetail can reference PostResponse.
ThreadDetail.model_rebuild()
