"""
backend/app/schemas/chat.py

Pydantic v2 request / response schemas for direct messaging (Feature 15).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Nested summaries ──────────────────────────────────────────────────────────

class ChatUserSummary(BaseModel):
    """Lightweight user representation for chat search and conversation lists."""

    id: uuid.UUID
    full_name: str
    role: str

    model_config = {"from_attributes": True}


# ── Conversation schemas ─────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    """Payload sent when starting (or re-opening) a conversation."""

    recipient_id: str


class ConversationListItem(BaseModel):
    """Single conversation in the conversations list."""

    id: uuid.UUID
    participant_ids: List[str]
    created_at: datetime
    last_message_at: datetime
    last_message_preview: str
    last_message_sender_id: Optional[str] = None
    other_participant: Optional[ChatUserSummary] = None
    unread_count: int = 0

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Returned after creating / fetching a conversation."""

    id: uuid.UUID
    participant_ids: List[str]
    participant_key: str
    created_at: datetime
    last_message_at: datetime
    last_message_preview: str
    last_message_sender_id: Optional[str] = None
    other_participant: Optional[ChatUserSummary] = None

    model_config = {"from_attributes": True}


# ── Message schemas ──────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    """Payload sent when sending a chat message."""

    body: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """Single message returned in a conversation's message list."""

    id: uuid.UUID
    conversation_id: str
    sender_id: str
    sender_role: str
    recipient_id: str
    body: str
    created_at: datetime
    read_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

    model_config = {"from_attributes": True}
