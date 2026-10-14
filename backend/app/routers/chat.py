"""
backend/app/routers/chat.py

Direct / chat messaging endpoints (Feature 15).

Prefix: /api/v1/chat
Tags:   ["chat"]
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.schemas.chat import (
    ChatUserSummary,
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.services.chat_service import (
    CHAT_ALLOWED_ROLES,
    build_participant_key,
    require_chat_role,
    verify_conversation_participant,
)
from app.services.communication_metadata import (
    compute_response_latency_seconds,
    compute_text_stats,
)
from app.services.message_export_bridge import export_chat_message

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── GET /users ────────────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=List[ChatUserSummary],
    summary="Search users to chat with",
)
async def search_chat_users(
    search: Optional[str] = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[ChatUserSummary]:
    require_chat_role(current_user)

    uid = str(current_user.id)
    allowed_role_values = [r.value for r in CHAT_ALLOWED_ROLES]

    query_filter: dict = {
        "_id": {"$ne": uid},
        "is_active": True,
        "role": {"$in": allowed_role_values},
    }

    if search:
        query_filter["full_name"] = {"$regex": search, "$options": "i"}

    cursor = db.users.find(
        query_filter,
        {"_id": 1, "id": 1, "full_name": 1, "role": 1},
    ).limit(limit)

    results: list[ChatUserSummary] = []
    for u in await cursor.to_list(length=limit):
        results.append(ChatUserSummary(
            id=u.get("_id") or u.get("id"),
            full_name=u.get("full_name", "Unknown"),
            role=u.get("role", "student"),
        ))
    return results


# ── GET /conversations ────────────────────────────────────────────────────────

@router.get(
    "/conversations",
    response_model=List[ConversationListItem],
    summary="List my conversations",
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[ConversationListItem]:
    require_chat_role(current_user)

    uid = str(current_user.id)

    # Fetch conversations sorted by last_message_at desc.
    cursor = (
        db.chat_conversations
        .find({"participant_ids": uid})
        .sort("last_message_at", -1)
    )
    convs = await cursor.to_list(length=200)

    if not convs:
        return []

    # Compute unread counts in ONE aggregation.
    conv_ids = [c["_id"] for c in convs]
    pipeline = [
        {
            "$match": {
                "conversation_id": {"$in": conv_ids},
                "recipient_id": uid,
                "read_at": None,
            }
        },
        {"$group": {"_id": "$conversation_id", "count": {"$sum": 1}}},
    ]
    unread_agg = await db.chat_messages.aggregate(pipeline).to_list(length=len(conv_ids))
    unread_map = {item["_id"]: item["count"] for item in unread_agg}

    # Bulk-load other participants.
    other_ids: set[str] = set()
    for c in convs:
        for pid in c.get("participant_ids", []):
            if pid != uid:
                other_ids.add(pid)

    others_map: dict[str, ChatUserSummary] = {}
    if other_ids:
        ucursor = db.users.find(
            {"_id": {"$in": list(other_ids)}},
            {"_id": 1, "id": 1, "full_name": 1, "role": 1},
        )
        for u in await ucursor.to_list(length=len(other_ids)):
            oid = u.get("_id") or u.get("id")
            others_map[oid] = ChatUserSummary(
                id=oid,
                full_name=u.get("full_name", "Unknown"),
                role=u.get("role", "student"),
            )
        # Fallback for id field
        missing = other_ids - set(others_map.keys())
        if missing:
            ucursor2 = db.users.find(
                {"id": {"$in": list(missing)}},
                {"_id": 1, "id": 1, "full_name": 1, "role": 1},
            )
            for u in await ucursor2.to_list(length=len(missing)):
                oid = u.get("id") or u.get("_id")
                others_map[oid] = ChatUserSummary(
                    id=oid,
                    full_name=u.get("full_name", "Unknown"),
                    role=u.get("role", "student"),
                )

    results: list[ConversationListItem] = []
    for c in convs:
        other_id = next((p for p in c.get("participant_ids", []) if p != uid), None)
        c["other_participant"] = others_map.get(other_id) if other_id else None
        c["unread_count"] = unread_map.get(c["_id"], 0)
        results.append(ConversationListItem(**c))

    return results


# ── POST /conversations ──────────────────────────────────────────────────────

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume a conversation",
)
async def create_or_get_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConversationResponse:
    require_chat_role(current_user)

    uid = str(current_user.id)
    rid = payload.recipient_id

    if uid == rid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot start a conversation with yourself.",
        )

    # Verify recipient exists, is active, and has an allowed role.
    recipient_doc = await db.users.find_one({"_id": rid})
    if not recipient_doc:
        recipient_doc = await db.users.find_one({"id": rid})
    if not recipient_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient user not found.",
        )
    if not recipient_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipient user is inactive.",
        )

    allowed_role_values = {r.value for r in CHAT_ALLOWED_ROLES}
    recipient_role = recipient_doc.get("role", "")
    if recipient_role not in allowed_role_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The recipient's role does not support chat.",
        )

    pkey = build_participant_key(uid, rid)
    sorted_ids = sorted([uid, rid])

    # Idempotent: return existing conversation if present.
    existing = await db.chat_conversations.find_one({"participant_key": pkey})
    if existing:
        other = ChatUserSummary(
            id=recipient_doc.get("_id") or recipient_doc.get("id"),
            full_name=recipient_doc.get("full_name", "Unknown"),
            role=recipient_doc.get("role", "student"),
        )
        existing["other_participant"] = other
        return ConversationResponse(**existing)

    # Create new conversation.
    now = datetime.now(timezone.utc)
    cid = str(uuid.uuid4())
    conv_doc = {
        "_id": cid,
        "id": cid,
        "participant_ids": sorted_ids,
        "participant_key": pkey,
        "created_at": now,
        "last_message_at": now,
        "last_message_preview": "",
        "last_message_sender_id": None,
    }

    try:
        await db.chat_conversations.insert_one(conv_doc)
    except DuplicateKeyError:
        # Race condition: another request created it first.
        existing = await db.chat_conversations.find_one({"participant_key": pkey})
        if existing:
            other = ChatUserSummary(
                id=recipient_doc.get("_id") or recipient_doc.get("id"),
                full_name=recipient_doc.get("full_name", "Unknown"),
                role=recipient_doc.get("role", "student"),
            )
            existing["other_participant"] = other
            return ConversationResponse(**existing)

    other = ChatUserSummary(
        id=recipient_doc.get("_id") or recipient_doc.get("id"),
        full_name=recipient_doc.get("full_name", "Unknown"),
        role=recipient_doc.get("role", "student"),
    )
    conv_doc["other_participant"] = other
    return ConversationResponse(**conv_doc)


# ── GET /conversations/{conversation_id}/messages ─────────────────────────────

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="Get messages in a conversation",
)
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(None, description="Message ID cursor for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[MessageResponse]:
    require_chat_role(current_user)

    cid = str(conversation_id)
    await verify_conversation_participant(db, cid, current_user)

    query_filter: dict = {"conversation_id": cid}

    if before:
        # Find the cursor message to get its created_at.
        cursor_msg = await db.chat_messages.find_one({"_id": before})
        if not cursor_msg:
            cursor_msg = await db.chat_messages.find_one({"id": before})
        if cursor_msg:
            query_filter["created_at"] = {"$lt": cursor_msg["created_at"]}

    # Fetch the latest `limit` messages (descending), then reverse for asc order.
    cursor = (
        db.chat_messages
        .find(query_filter)
        .sort("created_at", -1)
        .limit(limit)
    )
    messages = await cursor.to_list(length=limit)
    messages.reverse()  # ascending created_at

    return [MessageResponse(**m) for m in messages]


# ── POST /conversations/{conversation_id}/read ──────────────────────────────

@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark messages as read",
)
async def mark_messages_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> None:
    require_chat_role(current_user)

    cid = str(conversation_id)
    await verify_conversation_participant(db, cid, current_user)

    uid = str(current_user.id)
    now = datetime.now(timezone.utc)

    await db.chat_messages.update_many(
        {
            "conversation_id": cid,
            "recipient_id": uid,
            "read_at": None,
        },
        {"$set": {"read_at": now}},
    )


# ── POST /conversations/{conversation_id}/messages ───────────────────────────

@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MessageResponse:
    require_chat_role(current_user)

    cid = str(conversation_id)
    conv = await verify_conversation_participant(db, cid, current_user)

    uid = str(current_user.id)
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Determine recipient (the other participant).
    recipient_id = next(
        (p for p in conv.get("participant_ids", []) if p != uid),
        None,
    )
    if not recipient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine recipient.",
        )

    body = payload.body.strip()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message body cannot be empty.",
        )

    now = datetime.now(timezone.utc)

    # Compute response latency: only if the most recent message was from
    # the OTHER participant (not a consecutive message from the sender).
    latency = None
    last_msg = await db.chat_messages.find_one(
        {"conversation_id": cid},
        sort=[("created_at", -1)],
    )
    if last_msg and last_msg.get("sender_id") != uid:
        latency = compute_response_latency_seconds(
            last_msg.get("created_at"), now
        )

    stats = compute_text_stats(body)
    metadata = {
        **stats,
        "response_latency_seconds": latency,
    }

    mid = str(uuid.uuid4())
    msg_doc = {
        "_id": mid,
        "id": mid,
        "conversation_id": cid,
        "sender_id": uid,
        "sender_role": role_val,
        "recipient_id": recipient_id,
        "body": body,
        "created_at": now,
        "read_at": None,
        "metadata": metadata,
    }

    await db.chat_messages.insert_one(msg_doc)
    await export_chat_message(db, msg_doc, current_user)

    # Update conversation last_message_* fields.
    preview = body[:80]
    await db.chat_conversations.update_one(
        {"_id": cid},
        {
            "$set": {
                "last_message_at": now,
                "last_message_preview": preview,
                "last_message_sender_id": uid,
            }
        },
    )

    return MessageResponse(**msg_doc)
