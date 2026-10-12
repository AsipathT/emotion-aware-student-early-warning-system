"""
backend/app/models/chat.py

MongoDB document models for direct / chat messaging (Feature 15).

Collections
-----------
- **chat_conversations** – one document per unique pair of participants.
- **chat_messages** – individual messages within a conversation.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatConversation(BaseModel):
    """Document stored in the ``chat_conversations`` collection."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    participant_ids: List[str] = Field(default_factory=list)
    participant_key: str = ""  # "idA:idB" sorted, unique index
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_preview: str = ""
    last_message_sender_id: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        cid = str(self.id)
        return {
            "_id": cid,
            "id": cid,
            "participant_ids": self.participant_ids,
            "participant_key": self.participant_key,
            "created_at": self.created_at,
            "last_message_at": self.last_message_at,
            "last_message_preview": self.last_message_preview,
            "last_message_sender_id": self.last_message_sender_id,
        }


class ChatMessage(BaseModel):
    """Document stored in the ``chat_messages`` collection."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: str
    sender_id: str
    sender_role: str
    recipient_id: str
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True, "populate_by_name": True}

    def to_mongo(self) -> dict:
        """Converts model to dictionary ready for MongoDB insertion."""
        mid = str(self.id)
        return {
            "_id": mid,
            "id": mid,
            "conversation_id": self.conversation_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "recipient_id": self.recipient_id,
            "body": self.body,
            "created_at": self.created_at,
            "read_at": self.read_at,
            "metadata": self.metadata,
        }
