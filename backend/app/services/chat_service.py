"""
backend/app/services/chat_service.py

Business-logic helpers for the chat feature (Feature 15).

Keeps the router thin by encapsulating:
- participant key construction
- conversation participant verification
- allowed-role gating
"""

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import User, UserRole

# Roles that may use chat.
CHAT_ALLOWED_ROLES = frozenset({UserRole.STUDENT, UserRole.LECTURER, UserRole.COUNSELLOR})


def build_participant_key(id_a: str, id_b: str) -> str:
    """
    Create a deterministic, sorted key for a pair of user IDs.

    The ``chat_conversations`` collection has a unique index on this field
    so that only one conversation document can exist per pair.
    """
    return ":".join(sorted([id_a, id_b]))


def require_chat_role(user: User) -> None:
    """Raise 403 if the user's role is not allowed to use chat."""
    if user.role not in CHAT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not have access to chat.",
        )


async def verify_conversation_participant(
    db: AsyncIOMotorDatabase,
    conversation_id: str,
    user: User,
) -> dict:
    """
    Load a conversation and verify the user is one of the two participants.

    Returns
    -------
    dict
        The conversation document.

    Raises
    ------
    HTTPException 404
        Conversation not found.
    HTTPException 403
        User is not a participant.
    """
    conv = await db.chat_conversations.find_one({"_id": conversation_id})
    if not conv:
        conv = await db.chat_conversations.find_one({"id": conversation_id})
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    uid = str(user.id)
    if uid not in conv.get("participant_ids", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation.",
        )

    return conv
