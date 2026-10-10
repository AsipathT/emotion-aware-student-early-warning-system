"""
backend/app/core/privacy.py

Feature 5: Pseudonymization and anonymization layer.
Provides:
  - pseudonymize(student_id): Deterministic HMAC-SHA256 pseudonym generator.
  - scrub_text(text, known_names): Multi-stage PII scrubber replacing emails,
    phones, URLs, registration IDs, and personal names with redaction tags.
"""

import hashlib
import hmac
import re
from typing import Dict, List, Optional, Tuple

import spacy

from app.core.config import settings

# ── Pre-compiled Regular Expressions ──────────────────────────────────────────
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)

URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s<>"]+',
    re.IGNORECASE,
)

# Student registration ID: case-insensitive IT followed by 8 digits
REG_ID_REGEX = re.compile(
    r'(?i)\bIT\d{8}\b'
)

# Phone numbers (international, local with dashes, brackets, spaces)
PHONE_REGEX = re.compile(
    r'(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)\d{3,4}[-.\s]?\d{3,4}\b'
)

# Placeholder tags and identifiers to prevent re-redaction
PLACEHOLDER_WORDS = {"NAME", "EMAIL", "PHONE", "URL", "REG_ID"}
PLACEHOLDER_TAGS = {"[NAME]", "[EMAIL]", "[PHONE]", "[URL]", "[REG_ID]"}

# ── Lazy-loaded spaCy model ───────────────────────────────────────────────────
_nlp = None


def get_nlp():
    """Returns the loaded spaCy en_core_web_sm pipeline."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            import spacy.cli
            spacy.cli.download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ── Deterministic Pseudonymization ────────────────────────────────────────────

# Student Pseudonym ID format: STU_ followed by exactly 8 hex characters
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
    settings.PSEUDONYM_SECRET_KEY.

    Returns the prefix "STU_" followed by the first 8 characters of the hex digest.
    Example: STU_a1b2c3d4
    """
    secret = settings.PSEUDONYM_SECRET_KEY.encode("utf-8")
    data = str(student_id).strip().encode("utf-8")
    digest = hmac.new(secret, data, hashlib.sha256).hexdigest()
    return f"STU_{digest[:8]}"


# ── Text Scrubber & Redaction ─────────────────────────────────────────────────

def scrub_text(
    text: str,
    known_names: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, int]]:
    """
    Scans free text, redacts sensitive identifiers, and produces an audit report.

    Redaction Rules:
      1. Emails            -> [EMAIL]
      2. Phone numbers     -> [PHONE]
      3. URLs              -> [URL]
      4. Registration IDs  -> [REG_ID] (e.g. IT12345678)
      5. Known Names       -> [NAME]
      6. spaCy PERSON entities -> [NAME]

    Returns:
      (clean_text, redaction_report)
    """
    redaction_report: Dict[str, int] = {
        "EMAIL": 0,
        "PHONE": 0,
        "URL": 0,
        "REG_ID": 0,
        "NAME": 0,
    }

    if not text:
        return "", redaction_report

    clean_text = text

    # 1. Redact Emails
    email_matches = EMAIL_REGEX.findall(clean_text)
    if email_matches:
        redaction_report["EMAIL"] += len(email_matches)
        clean_text = EMAIL_REGEX.sub("[EMAIL]", clean_text)

    # 2. Redact URLs
    url_matches = URL_REGEX.findall(clean_text)
    if url_matches:
        redaction_report["URL"] += len(url_matches)
        clean_text = URL_REGEX.sub("[URL]", clean_text)

    # 3. Redact Registration IDs ((?i)IT\d{8})
    reg_matches = REG_ID_REGEX.findall(clean_text)
    if reg_matches:
        redaction_report["REG_ID"] += len(reg_matches)
        clean_text = REG_ID_REGEX.sub("[REG_ID]", clean_text)

    # 4. Redact Phone Numbers
    phone_matches = PHONE_REGEX.findall(clean_text)
    if phone_matches:
        redaction_report["PHONE"] += len(phone_matches)
        clean_text = PHONE_REGEX.sub("[PHONE]", clean_text)

    # 5. Exact match on known_names
    if known_names:
        sorted_names = sorted(
            [n.strip() for n in known_names if n and n.strip()],
            key=len,
            reverse=True,
        )
        for name in sorted_names:
            name_pattern = re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE)
            matches = name_pattern.findall(clean_text)
            if matches:
                redaction_report["NAME"] += len(matches)
                clean_text = name_pattern.sub("[NAME]", clean_text)

    # 6. spaCy NER Person Detection
    nlp = get_nlp()
    doc = nlp(clean_text)
    person_spans = []

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Check if this token is a placeholder word or tag
            ent_str = ent.text.strip()
            if ent_str in PLACEHOLDER_WORDS or ent_str in PLACEHOLDER_TAGS:
                continue

            # Check if it is enclosed inside square brackets e.g. [REG_ID]
            start, end = ent.start_char, ent.end_char
            if start > 0 and end < len(clean_text) and clean_text[start - 1] == "[" and clean_text[end] == "]":
                continue

            person_spans.append((start, end, ent_str))

    # Replace from back to front to maintain index offsets
    person_spans.sort(key=lambda s: s[0], reverse=True)
    for start, end, _ in person_spans:
        clean_text = clean_text[:start] + "[NAME]" + clean_text[end:]
        redaction_report["NAME"] += 1

    return clean_text, redaction_report


# ── Consent Verification Dependency ───────────────────────────────────────────

async def has_active_consent(pid: str, db) -> bool:
    """
    Checks if the student with `pid` has an active 'accepted' consent record
    for the currently active notice version. Queries the consent_records collection
    for the most recent entry under that version.
    """
    if not pid:
        return False

    active_notice = await db.consent_notices.find_one({"is_active": True})
    if not active_notice:
        return False

    active_version = active_notice.get("version", 1)

    latest_record = await db.consent_records.find_one(
        {"pid": pid, "notice_version": active_version},
        sort=[("timestamp", -1)],
    )

    if not latest_record:
        return False

    return latest_record.get("decision") == "accepted"
