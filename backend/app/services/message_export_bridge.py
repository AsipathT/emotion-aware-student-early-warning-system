"""
backend/app/services/message_export_bridge.py

Feature 17: Communication metadata capture (LMS -> C1 export bridge).
Best-effort write-through from LMS interactive communication features (Forum, Chat, Journal)
into the canonical MongoDB `messages` collection for Component 1 (Affective State Detection).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.privacy import EMAIL_REGEX, REG_ID_REGEX, is_valid_pid, scrub_text
from app.db import collections as col
from app.db.storage_models import TextMessageStorage
from app.schemas.contract.common import SourceType
from app.services.week_index import _ensure_utc, get_week_index

logger = logging.getLogger("app.services.message_export_bridge")


def _is_student(author_user: Any) -> bool:
    """Verifies that the author is an authenticated student."""
    role = getattr(author_user, "role", None)
    if role is None:
        return False
    role_val = role.value if hasattr(role, "value") else str(role)
    return role_val.strip().lower() == "student"


async def _resolve_student_pid(db: AsyncIOMotorDatabase, author_user: Any) -> Optional[str]:
    """
    Extracts the student PID from the User object or looks up the users collection by _id / id.
    Validates adherence to the Feature 5 pseudonym format (STU_xxxxxxxx).
    """
    pid = getattr(author_user, "pid", None)
    if pid and is_valid_pid(str(pid)):
        return str(pid).strip()

    uid = str(getattr(author_user, "id", "")).strip()
    if not uid:
        return None

    user_doc = await db[col.USERS].find_one({"_id": uid})
    if not user_doc:
        user_doc = await db[col.USERS].find_one({"id": uid})

    if user_doc and user_doc.get("pid"):
        candidate_pid = str(user_doc["pid"]).strip()
        if is_valid_pid(candidate_pid):
            return candidate_pid

    return None


def _prepare_clean_text(raw_text: str, author_name: Optional[str]) -> Optional[str]:
    """
    Scrubs text of personal identifiers and enforces CleanText constraints.
    Returns cleaned text string or None if empty/violating privacy safety nets.
    """
    if not raw_text or not raw_text.strip():
        return None

    known_names = [author_name.strip()] if author_name and author_name.strip() else None
    scrubbed, _ = scrub_text(raw_text, known_names=known_names)
    clean_text = scrubbed.strip()

    if not clean_text:
        return None

    # Safety net: Verify absence of unredacted email addresses or institutional registration IDs
    if EMAIL_REGEX.search(clean_text) or REG_ID_REGEX.search(clean_text):
        return None

    return clean_text


async def resolve_chat_course_id(
    db: AsyncIOMotorDatabase,
    sender_pid: str,
    sender_id: str,
    recipient_id: str,
) -> Optional[str]:
    """
    Resolves the associated course_id for a student chat message.

    Rule:
    1. Look up the sender's ACTIVE enrolments from canonical col.ENROLMENTS.
    2. A course matches if the recipient is that course's lecturer (courses.lecturer_id)
       OR the recipient is also an active student in that course.
    3. If exactly one course matches, use it.
    4. If several match, choose the one with the latest enrolment_start.
    5. If none match, log warning without identifiers and return None.
    """
    cursor = db[col.ENROLMENTS].find({"pid": sender_pid, "status": "active"})
    sender_enrolments = await cursor.to_list(length=500)
    if not sender_enrolments:
        logger.warning("chat export skipped: no shared course")
        return None

    recip_uid = str(recipient_id).strip()
    recip_user = await db[col.USERS].find_one({"_id": recip_uid})
    if not recip_user:
        recip_user = await db[col.USERS].find_one({"id": recip_uid})

    recip_pid = recip_user.get("pid") if recip_user else None

    matched_courses: List[Tuple[str, datetime]] = []

    for enr in sender_enrolments:
        cid = str(enr.get("course_id", "")).strip()
        if not cid:
            continue

        # Check if recipient is the lecturer for this course
        course_doc = await db[col.COURSES].find_one({"_id": cid})
        if not course_doc:
            course_doc = await db[col.COURSES].find_one({"id": cid})

        is_lecturer = bool(
            course_doc and str(course_doc.get("lecturer_id", "")).strip() == recip_uid
        )

        # Check if recipient is also an active enrolled student in this course
        is_fellow_student = False
        if recip_pid and is_valid_pid(str(recip_pid)):
            recip_enrol = await db[col.ENROLMENTS].find_one({
                "pid": str(recip_pid).strip(),
                "course_id": cid,
                "status": "active",
            })
            is_fellow_student = recip_enrol is not None

        if is_lecturer or is_fellow_student:
            start_raw = enr.get("enrolment_start")
            start_utc = _ensure_utc(start_raw) or datetime.min.replace(tzinfo=timezone.utc)
            matched_courses.append((cid, start_utc))

    if not matched_courses:
        logger.warning("chat export skipped: no shared course")
        return None

    if len(matched_courses) == 1:
        return matched_courses[0][0]

    # Multiple matching courses: select the course with latest enrolment_start
    matched_courses.sort(key=lambda x: x[1], reverse=True)
    return matched_courses[0][0]


async def _persist_text_message(
    db: AsyncIOMotorDatabase,
    source_id: str,
    pid: str,
    course_id: str,
    week_index: int,
    source_type: SourceType,
    clean_text: str,
    timestamp: datetime,
    response_latency: Optional[float],
    char_count: int,
    word_count: int,
    reply_to_id: Optional[str],
) -> bool:
    """Builds and upserts canonical TextMessageStorage document into messages collection."""
    storage_doc = TextMessageStorage(
        id=source_id,
        message_id=source_id,
        pid=pid,
        course_id=course_id,
        week_index=week_index,
        source_type=source_type,
        clean_text=clean_text,
        timestamp=timestamp,
        response_latency_seconds=response_latency,
        message_length_chars=char_count,
        message_length_words=word_count,
        reply_to_id=reply_to_id,
        source="lms",
        source_version="1.0",
    )
    doc_dict = storage_doc.model_dump(by_alias=True)
    if hasattr(doc_dict.get("source_type"), "value"):
        doc_dict["source_type"] = doc_dict["source_type"].value

    await db[col.MESSAGES].update_one(
        {"_id": source_id},
        {"$setOnInsert": doc_dict},
        upsert=True,
    )
    return True


async def export_forum_thread(
    db: AsyncIOMotorDatabase,
    thread_doc: Dict[str, Any],
    author_user: Any,
) -> bool:
    """
    Exports a student-authored forum thread to the canonical messages collection.
    Never raises an exception.
    """
    source_id = str(thread_doc.get("_id") or thread_doc.get("id", ""))
    try:
        if not _is_student(author_user):
            return False

        pid = await _resolve_student_pid(db, author_user)
        if not pid:
            logger.warning("Message export skipped: author PID missing or invalid for source_type=forum id=%s", source_id)
            return False

        course_id = str(thread_doc.get("course_id", "")).strip()
        if not course_id:
            logger.warning("Message export skipped: missing course_id for source_type=forum id=%s", source_id)
            return False

        clean_text = _prepare_clean_text(
            thread_doc.get("body", ""),
            getattr(author_user, "full_name", None),
        )
        if not clean_text:
            logger.warning("Message export skipped: text empty or violates CleanText for source_type=forum id=%s", source_id)
            return False

        created_at = _ensure_utc(thread_doc.get("created_at")) or datetime.now(timezone.utc)
        week_index = await get_week_index(db, course_id, created_at)

        metadata = thread_doc.get("metadata") or {}
        latency = metadata.get("response_latency_seconds")
        char_count = int(metadata.get("char_count", len(clean_text)))
        word_count = int(metadata.get("word_count", len(clean_text.split())))

        return await _persist_text_message(
            db=db,
            source_id=source_id,
            pid=pid,
            course_id=course_id,
            week_index=week_index,
            source_type=SourceType.FORUM,
            clean_text=clean_text,
            timestamp=created_at,
            response_latency=latency,
            char_count=char_count,
            word_count=word_count,
            reply_to_id=None,
        )
    except Exception as exc:
        logger.warning("Failed to export forum thread (id=%s): %s", source_id, type(exc).__name__)
        return False


async def export_forum_post(
    db: AsyncIOMotorDatabase,
    post_doc: Dict[str, Any],
    author_user: Any,
) -> bool:
    """
    Exports a student-authored forum post to the canonical messages collection.
    Never raises an exception.
    """
    source_id = str(post_doc.get("_id") or post_doc.get("id", ""))
    try:
        if not _is_student(author_user):
            return False

        pid = await _resolve_student_pid(db, author_user)
        if not pid:
            logger.warning("Message export skipped: author PID missing or invalid for source_type=forum id=%s", source_id)
            return False

        course_id = str(post_doc.get("course_id", "")).strip()
        if not course_id:
            logger.warning("Message export skipped: missing course_id for source_type=forum id=%s", source_id)
            return False

        clean_text = _prepare_clean_text(
            post_doc.get("body", ""),
            getattr(author_user, "full_name", None),
        )
        if not clean_text:
            logger.warning("Message export skipped: text empty or violates CleanText for source_type=forum id=%s", source_id)
            return False

        created_at = _ensure_utc(post_doc.get("created_at")) or datetime.now(timezone.utc)
        week_index = await get_week_index(db, course_id, created_at)

        metadata = post_doc.get("metadata") or {}
        latency = metadata.get("response_latency_seconds")
        char_count = int(metadata.get("char_count", len(clean_text)))
        word_count = int(metadata.get("word_count", len(clean_text.split())))

        parent_post_id = post_doc.get("parent_post_id")
        thread_id = post_doc.get("thread_id")
        reply_to_id = str(parent_post_id) if parent_post_id else (str(thread_id) if thread_id else None)

        return await _persist_text_message(
            db=db,
            source_id=source_id,
            pid=pid,
            course_id=course_id,
            week_index=week_index,
            source_type=SourceType.FORUM,
            clean_text=clean_text,
            timestamp=created_at,
            response_latency=latency,
            char_count=char_count,
            word_count=word_count,
            reply_to_id=reply_to_id,
        )
    except Exception as exc:
        logger.warning("Failed to export forum post (id=%s): %s", source_id, type(exc).__name__)
        return False


async def export_chat_message(
    db: AsyncIOMotorDatabase,
    msg_doc: Dict[str, Any],
    author_user: Any,
) -> bool:
    """
    Exports a student-sent chat message to the canonical messages collection.
    Never raises an exception.
    """
    source_id = str(msg_doc.get("_id") or msg_doc.get("id", ""))
    try:
        if not _is_student(author_user):
            return False

        pid = await _resolve_student_pid(db, author_user)
        if not pid:
            logger.warning("Message export skipped: author PID missing or invalid for source_type=chat id=%s", source_id)
            return False

        recipient_id = str(msg_doc.get("recipient_id", "")).strip()
        sender_id = str(getattr(author_user, "id", "")).strip()
        course_id = await resolve_chat_course_id(
            db=db,
            sender_pid=pid,
            sender_id=sender_id,
            recipient_id=recipient_id,
        )
        if not course_id:
            # resolve_chat_course_id already logs warning without identifiers
            return False

        clean_text = _prepare_clean_text(
            msg_doc.get("body", ""),
            getattr(author_user, "full_name", None),
        )
        if not clean_text:
            logger.warning("Message export skipped: text empty or violates CleanText for source_type=chat id=%s", source_id)
            return False

        created_at = _ensure_utc(msg_doc.get("created_at")) or datetime.now(timezone.utc)
        week_index = await get_week_index(db, course_id, created_at)

        metadata = msg_doc.get("metadata") or {}
        latency = metadata.get("response_latency_seconds")
        char_count = int(metadata.get("char_count", len(clean_text)))
        word_count = int(metadata.get("word_count", len(clean_text.split())))

        return await _persist_text_message(
            db=db,
            source_id=source_id,
            pid=pid,
            course_id=course_id,
            week_index=week_index,
            source_type=SourceType.CHAT,
            clean_text=clean_text,
            timestamp=created_at,
            response_latency=latency,
            char_count=char_count,
            word_count=word_count,
            reply_to_id=None,
        )
    except Exception as exc:
        logger.warning("Failed to export chat message (id=%s): %s", source_id, type(exc).__name__)
        return False


async def export_journal_entry(
    db: AsyncIOMotorDatabase,
    entry_doc: Dict[str, Any],
    author_user: Any,
) -> bool:
    """
    Exports a student journal entry to the canonical messages collection.
    Never raises an exception.
    """
    source_id = str(entry_doc.get("_id") or entry_doc.get("id", ""))
    try:
        if not _is_student(author_user):
            return False

        pid = await _resolve_student_pid(db, author_user)
        if not pid:
            logger.warning("Message export skipped: author PID missing or invalid for source_type=journal id=%s", source_id)
            return False

        course_id = str(entry_doc.get("course_id", "")).strip()
        if not course_id:
            logger.warning("Message export skipped: missing course_id for source_type=journal id=%s", source_id)
            return False

        clean_text = _prepare_clean_text(
            entry_doc.get("body", ""),
            getattr(author_user, "full_name", None),
        )
        if not clean_text:
            logger.warning("Message export skipped: text empty or violates CleanText for source_type=journal id=%s", source_id)
            return False

        created_at = _ensure_utc(entry_doc.get("created_at")) or datetime.now(timezone.utc)
        week_index = await get_week_index(db, course_id, created_at)

        metadata = entry_doc.get("metadata") or {}
        latency = metadata.get("response_latency_seconds")
        char_count = int(metadata.get("char_count", len(clean_text)))
        word_count = int(metadata.get("word_count", len(clean_text.split())))

        return await _persist_text_message(
            db=db,
            source_id=source_id,
            pid=pid,
            course_id=course_id,
            week_index=week_index,
            source_type=SourceType.JOURNAL,
            clean_text=clean_text,
            timestamp=created_at,
            response_latency=latency,
            char_count=char_count,
            word_count=word_count,
            reply_to_id=None,
        )
    except Exception as exc:
        logger.warning("Failed to export journal entry (id=%s): %s", source_id, type(exc).__name__)
        return False
