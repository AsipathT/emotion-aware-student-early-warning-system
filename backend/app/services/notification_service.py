"""
backend/app/services/notification_service.py

Feature 37: Student Notification Delivery & Safety Net (Component 4 Uptake Path).
Implements supportive student notifications, ethical non-stigmatizing text enforcement,
and multi-template dispatching.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.models.notification import (
    COL_NOTIFICATIONS,
    TYPE_SUPPORT_OFFERED,
    TYPE_APPOINTMENT_CONFIRMED,
    TYPE_MENTOR_ASSIGNED,
    TYPE_RESOURCE_SHARED,
    TYPE_FEEDBACK_REQUEST,
)

logger = logging.getLogger("app.notifications")

# Banned vocabulary list: ethics requirement prohibits revealing predictive or stigmatizing terms
BANNED_WORDS: List[str] = [
    "risk",
    "dropout",
    "drop out",
    "distress",
    "critical",
    "score",
    "tier",
    "anxiety",
    "helpless",
    "depress",
    "fail",
    "flagged",
    "predict",
]

GENERIC_SAFE_TITLE: str = "Academic Support Update"
GENERIC_SAFE_BODY: str = "Learning support and guidance resources are available for your studies."

NOTIFICATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    TYPE_SUPPORT_OFFERED: {
        "title": "Support Available: {student_label}",
        "body": "Supportive guidance and assistance for {student_label} are now available for your courses. Check your support options to get started.",
        "link": "/support",
    },
    TYPE_APPOINTMENT_CONFIRMED: {
        "title": "Advisory Appointment Confirmed",
        "body": "Your confidential student advisory consultation session has been scheduled for {scheduled_time}. We look forward to meeting with you.",
        "link": "/support",
    },
    TYPE_MENTOR_ASSIGNED: {
        "title": "Peer Mentorship Connection",
        "body": "A student peer mentor has been assigned to help guide you through your coursework and studies.",
        "link": "/messages",
    },
    TYPE_RESOURCE_SHARED: {
        "title": "Supplementary Learning Materials",
        "body": "Helpful study guides and revision exercises have been shared to assist with your academic goals.",
        "link": "/support",
    },
    TYPE_FEEDBACK_REQUEST: {
        "title": "How Was Your Recent Support Session?",
        "body": "We welcome your thoughts and feedback on your recent support consultation to help us improve.",
        "link": "/support",
    },
}


def is_text_safe(text: Optional[str]) -> bool:
    """
    Pure validation helper.
    Returns True if the input text contains zero banned phrases; False otherwise.
    """
    if not text:
        return True
    lower = str(text).lower()
    for word in BANNED_WORDS:
        if word in lower:
            return False
    return True


def assert_safe_text(text: Optional[str], is_title: bool = False) -> str:
    """
    Pure safety-net function.
    Inspects text for banned analytical or deficit terms.
    If any banned term is detected, suppresses it and returns a neutral generic message.
    """
    if not text:
        return ""
    if not is_text_safe(text):
        logger.warning(
            "[SAFETY NET: assert_safe_text] Deficit or predictive terminology detected in notification text. Sanitizing to generic supportive copy."
        )
        return GENERIC_SAFE_TITLE if is_title else GENERIC_SAFE_BODY
    return str(text)


async def create_notification(
    db: AsyncIOMotorDatabase,
    user_id: str,
    type: str,
    title: str,
    body: str,
    link: Optional[str] = None,
    related_id: Optional[str] = None,
    dedupe_key: Optional[str] = None,
) -> bool:
    """
    Persists an in-app notification for a designated user.
    NEVER raises: returns False on any error or duplicate key conflict.
    Logs warnings without logging notification text (ethics & privacy constraint).
    """
    try:
        clean_user_id = str(user_id).strip()
        if not clean_user_id:
            return False

        safe_title = assert_safe_text(title, is_title=True)
        safe_body = assert_safe_text(body, is_title=False)

        # Pre-check dedupe_key if specified
        if dedupe_key:
            existing = await db[COL_NOTIFICATIONS].find_one({"dedupe_key": str(dedupe_key)})
            if existing:
                return False

        notif_doc = {
            "id": str(uuid.uuid4()),
            "user_id": clean_user_id,
            "type": str(type).strip(),
            "title": safe_title,
            "body": safe_body,
            "link": link,
            "related_id": str(related_id) if related_id else None,
            "dedupe_key": str(dedupe_key) if dedupe_key else None,
            "created_at": datetime.now(timezone.utc),
            "read_at": None,
        }

        await db[COL_NOTIFICATIONS].insert_one(notif_doc)
        return True

    except DuplicateKeyError:
        # Dedupe key matched an existing document
        return False
    except Exception as exc:
        # Privacy invariant: do NOT print or log notification title/body content
        logger.warning(
            "[create_notification] Failed to create notification for user_id=%s, type=%s: %s",
            user_id,
            type,
            exc,
        )
        return False


async def notify_pid(
    db: AsyncIOMotorDatabase,
    pid: str,
    template_key: str,
    **vars: Any,
) -> bool:
    """
    Resolves users.pid to an active student user ID and dispatches a templated notification.
    Skips silently if no active user account is associated with the pseudonym.
    """
    try:
        clean_pid = str(pid).strip()
        if not clean_pid:
            return False

        user_doc = await db.users.find_one({"pid": clean_pid})
        if not user_doc or not user_doc.get("is_active", True):
            # Silently skip if student has no user account or is inactive
            return False

        user_id = str(user_doc.get("_id") or user_doc.get("id") or "")
        if not user_id:
            return False

        template = NOTIFICATION_TEMPLATES.get(template_key)
        if not template:
            logger.warning("[notify_pid] Unrecognized notification template key: %s", template_key)
            return False

        # Format title and body safely with provided variables
        try:
            raw_title = template["title"].format(**vars)
        except Exception:
            raw_title = template["title"]

        try:
            raw_body = template["body"].format(**vars)
        except Exception:
            raw_body = template["body"]

        link = vars.get("link") or template.get("link")
        related_id = vars.get("related_id")
        dedupe_key = vars.get("dedupe_key")

        return await create_notification(
            db=db,
            user_id=user_id,
            type=template_key,
            title=raw_title,
            body=raw_body,
            link=link,
            related_id=related_id,
            dedupe_key=dedupe_key,
        )

    except Exception as exc:
        logger.warning("[notify_pid] Unexpected dispatch failure for pid=%s: %s", pid, exc)
        return False
