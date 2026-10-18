"""
src/lms_client.py

Client library for communicating with LMS backend export endpoints.
Complies with contracts/v1/TextMessageRecord.json and export security protocols.
"""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("c1_lms_client")

DEFAULT_LMS_BASE_URL = "http://localhost:8000"


def fetch_messages(
    limit: int = 20,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    course_id: Optional[str] = None,
    week_index: Optional[int] = None,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Fetches scrubbed student messages from LMS endpoint:
    GET /api/v1/export/messages

    Headers:
      X-Component-Key: C1_COMPONENT_KEY
    """
    url_base = base_url or os.environ.get("LMS_BASE_URL", DEFAULT_LMS_BASE_URL)
    endpoint = f"{url_base.rstrip('/')}/api/v1/export/messages"

    key = api_key or os.environ.get("C1_COMPONENT_KEY")
    if not key:
        raise ValueError("C1_COMPONENT_KEY is not configured or provided.")

    headers = {
        "X-Component-Key": key,
        "Accept": "application/json",
    }

    params: Dict[str, Any] = {
        "page": 1,
        "page_size": min(limit, 500),
    }
    if course_id:
        params["course_id"] = course_id
    if week_index is not None:
        params["week_from"] = week_index
        params["week_to"] = week_index

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(endpoint, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()

        # Unwrap Envelope
        data = payload.get("data", [])
        logger.info(f"Successfully retrieved {len(data)} messages from LMS export endpoint")
        return data

    except httpx.HTTPStatusError as e:
        logger.error(f"LMS API returned HTTP error: {e.response.status_code}")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to LMS API at {endpoint}: {e}")
        raise
