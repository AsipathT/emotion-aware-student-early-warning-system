"""
backend/app/routers/forum.py

Discussion forum endpoints (Feature 14).

Prefix: /api/v1/forum
Tags:   ["forum"]
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.schemas.forum import (
    AuthorSummary,
    PostCreate,
    PostResponse,
    ThreadCreate,
    ThreadDetail,
    ThreadListItem,
    ThreadModerationUpdate,
)
from app.services.communication_metadata import (
    compute_response_latency_seconds,
    compute_text_stats,
)
from app.services.forum_access import (
    verify_forum_access,
    verify_forum_access_by_thread,
)
from app.services.message_export_bridge import (
    export_forum_post,
    export_forum_thread,
)

router = APIRouter(prefix="/api/v1/forum", tags=["forum"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _bulk_author_summaries(
    db: AsyncIOMotorDatabase,
    author_ids: set[str],
) -> dict[str, AuthorSummary]:
    """
    Fetch user docs for a set of author IDs in ONE query (no N+1).
    Returns a mapping ``{user_id_str: AuthorSummary}``.
    """
    if not author_ids:
        return {}

    cursor = db.users.find(
        {"_id": {"$in": list(author_ids)}},
        {"_id": 1, "id": 1, "full_name": 1, "role": 1},
    )
    users = await cursor.to_list(length=len(author_ids))

    result: dict[str, AuthorSummary] = {}
    for u in users:
        uid = u.get("_id") or u.get("id")
        result[uid] = AuthorSummary(
            id=uid,
            full_name=u.get("full_name", "Unknown"),
            role=u.get("role", "student"),
        )

    # Fallback: try `id` field for any authors not found via `_id`.
    missing = author_ids - set(result.keys())
    if missing:
        cursor2 = db.users.find(
            {"id": {"$in": list(missing)}},
            {"_id": 1, "id": 1, "full_name": 1, "role": 1},
        )
        for u in await cursor2.to_list(length=len(missing)):
            uid = u.get("id") or u.get("_id")
            result[uid] = AuthorSummary(
                id=uid,
                full_name=u.get("full_name", "Unknown"),
                role=u.get("role", "student"),
            )

    return result


# ── GET /courses/{course_id}/threads ──────────────────────────────────────────

@router.get(
    "/courses/{course_id}/threads",
    response_model=List[ThreadListItem],
    summary="List threads in a course forum",
)
async def list_threads(
    course_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[ThreadListItem]:
    cid = str(course_id)
    await verify_forum_access(db, cid, current_user, write=False)

    query_filter: dict = {"course_id": cid}
    if search:
        # Case-insensitive substring match on title or body.
        query_filter["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"body": {"$regex": search, "$options": "i"}},
        ]

    # Pinned threads first, then by most recent activity.
    cursor = (
        db.forum_threads
        .find(query_filter)
        .sort([("is_pinned", -1), ("last_activity_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    threads = await cursor.to_list(length=limit)

    # Bulk-load author summaries.
    author_ids = {t["author_id"] for t in threads}
    authors = await _bulk_author_summaries(db, author_ids)

    results: list[ThreadListItem] = []
    for t in threads:
        t["author"] = authors.get(t["author_id"])
        results.append(ThreadListItem(**t))

    return results


# ── POST /courses/{course_id}/threads ─────────────────────────────────────────

@router.post(
    "/courses/{course_id}/threads",
    response_model=ThreadListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new thread",
)
async def create_thread(
    course_id: uuid.UUID,
    payload: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ThreadListItem:
    cid = str(course_id)
    await verify_forum_access(db, cid, current_user, write=True)

    now = datetime.now(timezone.utc)
    uid = str(current_user.id)
    tid = str(uuid.uuid4())
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    stats = compute_text_stats(payload.body)

    thread_doc = {
        "_id": tid,
        "id": tid,
        "course_id": cid,
        "author_id": uid,
        "author_role": role_val,
        "title": payload.title,
        "body": payload.body,
        "created_at": now,
        "updated_at": now,
        "last_activity_at": now,
        "reply_count": 0,
        "is_pinned": False,
        "is_locked": False,
        "metadata": stats,
    }

    await db.forum_threads.insert_one(thread_doc)
    await export_forum_thread(db, thread_doc, current_user)

    thread_doc["author"] = AuthorSummary(
        id=uid,
        full_name=current_user.full_name,
        role=role_val,
    )
    return ThreadListItem(**thread_doc)


# ── GET /threads/{thread_id} ─────────────────────────────────────────────────

@router.get(
    "/threads/{thread_id}",
    response_model=ThreadDetail,
    summary="Get thread with all posts",
)
async def get_thread_detail(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ThreadDetail:
    tid = str(thread_id)
    thread, _course = await verify_forum_access_by_thread(db, tid, current_user, write=False)

    # Fetch all posts for this thread, ordered chronologically.
    posts_cursor = db.forum_posts.find({"thread_id": tid}).sort("created_at", 1)
    posts = await posts_cursor.to_list(length=10_000)

    # Bulk-load author summaries for the thread author + all post authors.
    author_ids = {thread["author_id"]} | {p["author_id"] for p in posts}
    authors = await _bulk_author_summaries(db, author_ids)

    thread["author"] = authors.get(thread["author_id"])

    post_responses: list[PostResponse] = []
    for p in posts:
        p["author"] = authors.get(p["author_id"])
        post_responses.append(PostResponse(**p))

    thread["posts"] = post_responses
    return ThreadDetail(**thread)


# ── POST /threads/{thread_id}/posts ──────────────────────────────────────────

@router.post(
    "/threads/{thread_id}/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a thread",
)
async def create_post(
    thread_id: uuid.UUID,
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PostResponse:
    tid = str(thread_id)
    thread, _course = await verify_forum_access_by_thread(db, tid, current_user, write=True)

    # Locked-thread guard.
    if thread.get("is_locked", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This thread is locked. New replies are not accepted.",
        )

    now = datetime.now(timezone.utc)
    uid = str(current_user.id)
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Determine what this post is replying to (for response-latency calc).
    replied_to_created_at = thread.get("created_at")
    replied_to_author_id = thread.get("author_id")

    if payload.parent_post_id:
        parent = await db.forum_posts.find_one({"_id": payload.parent_post_id})
        if not parent:
            parent = await db.forum_posts.find_one({"id": payload.parent_post_id})
        if not parent or parent.get("thread_id") != tid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_post_id does not belong to this thread.",
            )
        replied_to_created_at = parent.get("created_at")
        replied_to_author_id = parent.get("author_id")

    stats = compute_text_stats(payload.body)
    latency = compute_response_latency_seconds(replied_to_created_at, now)

    metadata = {
        **stats,
        "response_latency_seconds": latency,
        "replied_to_author_id": replied_to_author_id,
    }

    pid = str(uuid.uuid4())
    post_doc = {
        "_id": pid,
        "id": pid,
        "thread_id": tid,
        "course_id": thread["course_id"],
        "author_id": uid,
        "author_role": role_val,
        "parent_post_id": payload.parent_post_id,
        "body": payload.body,
        "created_at": now,
        "metadata": metadata,
    }

    await db.forum_posts.insert_one(post_doc)
    await export_forum_post(db, post_doc, current_user)

    # Update thread counters atomically.
    await db.forum_threads.update_one(
        {"_id": tid},
        {
            "$inc": {"reply_count": 1},
            "$set": {"last_activity_at": now, "updated_at": now},
        },
    )

    post_doc["author"] = AuthorSummary(
        id=uid,
        full_name=current_user.full_name,
        role=role_val,
    )
    return PostResponse(**post_doc)


# ── PATCH /threads/{thread_id}/moderation ────────────────────────────────────

@router.patch(
    "/threads/{thread_id}/moderation",
    response_model=ThreadListItem,
    summary="Pin or lock a thread (lecturer / admin)",
)
async def moderate_thread(
    thread_id: uuid.UUID,
    payload: ThreadModerationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ThreadListItem:
    tid = str(thread_id)
    thread, course = await verify_forum_access_by_thread(db, tid, current_user, write=True)

    # Only the course lecturer or admin may moderate.
    uid = str(current_user.id)
    is_course_lecturer = (
        current_user.role == UserRole.LECTURER
        and str(course.get("lecturer_id")) == uid
    )
    if not (current_user.role == UserRole.ADMIN or is_course_lecturer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course lecturer or an admin can moderate threads.",
        )

    updates: dict = {"updated_at": datetime.now(timezone.utc)}
    if payload.is_pinned is not None:
        updates["is_pinned"] = payload.is_pinned
    if payload.is_locked is not None:
        updates["is_locked"] = payload.is_locked

    if len(updates) == 1:
        # Only updated_at, nothing meaningful to change.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of is_pinned or is_locked.",
        )

    await db.forum_threads.update_one({"_id": tid}, {"$set": updates})

    # Return updated thread.
    updated = await db.forum_threads.find_one({"_id": tid})
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found after update.",
        )
    authors = await _bulk_author_summaries(db, {updated["author_id"]})
    updated["author"] = authors.get(updated["author_id"])
    return ThreadListItem(**updated)
