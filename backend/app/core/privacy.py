"""
backend/app/core/privacy.py

Feature 5: Pseudonymization and anonymization layer.
Provides:
  - pseudonymize(student_id): Deterministic HMAC-SHA256 pseudonym generator.
"""

import hashlib
import hmac
import os
import re
from typing import Optional

from app.core.config import settings

PID_REGEX = re.compile(r"^STU_[0-9a-fA-F]{8}$")


def is_valid_pid(pid: str) -> bool:
    """
    Validates whether a given string adheres to the Feature 5 student pseudonym
    format: prefix 'STU_' followed by the first 8 hex characters of HMAC-SHA256.
    """
    return bool(isinstance(pid, str) and PID_REGEX.match(pid.strip()))


def pseudonymize(student_id: str) -> str:
    """
    Creates a deterministic HMAC-SHA256 hash of the student_id using
    settings.PSEUDONYM_SECRET_KEY (or fallback default).

    Returns the prefix "STU_" followed by the first 8 characters of the hex digest.
    Example: STU_a1b2c3d4
    """
    secret_str = getattr(
        settings,
        "PSEUDONYM_SECRET_KEY",
        os.environ.get("PSEUDONYM_SECRET_KEY", "lms_pseudonym_hmac_secret_key_2026_super_secure"),
    )
    secret = secret_str.encode("utf-8")
    data = str(student_id).strip().encode("utf-8")
    digest = hmac.new(secret, data, hashlib.sha256).hexdigest()
    return f"STU_{digest[:8]}"
