"""
backend/app/pipeline/webhooks.py

HMAC-signed webhook dispatching for Feature 22: Weekly scheduler / pipeline orchestrator.
Sends notification events to downstream ML components when their prerequisite stages
become ready. Supports exponential backoff retries and never leaks student PII.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.pipeline.clock import get_clock

logger = logging.getLogger("app.pipeline.webhooks")


def sign_payload(secret: str, timestamp_str: str, body_str: str) -> str:
    """Computes HMAC-SHA256 signature formatted as sha256=<hex_digest>."""
    message = f"{timestamp_str}.{body_str}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def dispatch_stage_ready_webhook(
    component: str,
    course_id: str,
    week_index: int,
    run_id: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Dispatches a 'stage_ready' webhook event to the configured component endpoint, if any.
    Returns:
        {
            "notified": bool,
            "attempts": int,
            "error": Optional[str],
            "notified_at": Optional[datetime],
        }
    """
    if now is None:
        now = get_clock()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    webhooks_map = settings.COMPONENT_WEBHOOKS
    url = webhooks_map.get(component.lower())

    # If no webhook URL is configured for this component, return clean unnotified status
    if not url:
        return {
            "notified": False,
            "attempts": 0,
            "error": None,
            "notified_at": None,
        }

    payload = {
        "event": "stage_ready",
        "component": component.lower(),
        "course_id": course_id,
        "week_index": week_index,
        "run_id": run_id,
        "schema_version": 1,
        "generated_at": now.isoformat(),
    }
    body_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    ts_str = now.isoformat()

    headers = {
        "Content-Type": "application/json",
        "X-LMS-Timestamp": ts_str,
    }

    signing_secret = settings.WEBHOOK_SIGNING_SECRET
    if signing_secret:
        headers["X-LMS-Signature"] = sign_payload(signing_secret, ts_str, body_str)

    max_retries = max(1, settings.WEBHOOK_MAX_RETRIES)
    timeout = settings.WEBHOOK_TIMEOUT_SECONDS

    last_error: Optional[str] = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, content=body_str, headers=headers)
                if 200 <= response.status_code < 300:
                    return {
                        "notified": True,
                        "attempts": attempt,
                        "error": None,
                        "notified_at": now,
                    }
                else:
                    last_error = f"HTTP {response.status_code}"
        except httpx.RequestError as exc:
            # Mask any internal sensitive network details
            last_error = f"Network error: {type(exc).__name__}"
        except Exception as exc:
            last_error = f"Dispatch error: {type(exc).__name__}"

        if attempt < max_retries:
            # Exponential backoff: 0.05s * 2^(attempt - 1)
            await asyncio.sleep(0.05 * (2 ** (attempt - 1)))

    logger.warning(
        "Webhook dispatch failed for component %s (course %s, week %d) after %d attempts: %s",
        component,
        course_id,
        week_index,
        max_retries,
        last_error,
    )

    return {
        "notified": False,
        "attempts": max_retries,
        "error": last_error,
        "notified_at": None,
    }
