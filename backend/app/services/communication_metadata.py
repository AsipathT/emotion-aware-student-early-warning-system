"""
backend/app/services/communication_metadata.py

Reusable helpers for computing communication metadata that feeds C1
(Affective State Detection).  Used by the discussion forum, direct/chat
messaging, and reflective learning journal features.

Functions are *pure* (no DB or I/O) so they are easy to unit-test.
"""

from datetime import datetime, timezone
from typing import Optional


# ── Text statistics ───────────────────────────────────────────────────────────

def compute_text_stats(text: str) -> dict:
    """
    Return character count and word count for a piece of text.

    C1 uses message-length history to detect "message-length shrinkage",
    a marker of disengagement or distress.

    >>> compute_text_stats("Hello world")
    {'char_count': 11, 'word_count': 2}
    """
    return {
        "char_count": len(text),
        "word_count": len(text.split()),
    }


# ── Response latency ─────────────────────────────────────────────────────────

def _ensure_utc(dt: datetime) -> datetime:
    """
    Normalise a datetime to UTC-aware.

    Motor's default client is **not** tz_aware, so datetimes read from
    MongoDB are naive (but represent UTC).  This function adds the UTC
    tzinfo when it is missing, and leaves aware datetimes untouched.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_response_latency_seconds(
    earlier: Optional[datetime],
    later: Optional[datetime],
) -> Optional[float]:
    """
    Compute the number of seconds between two timestamps.

    Returns ``None`` when either timestamp is missing (e.g. the first
    message in a conversation has no predecessor).

    C1 uses latency-shift patterns (large or increasing delays) as a
    hedging / disengagement signal.

    Both naive and aware datetimes are accepted; naive ones are treated
    as UTC (see Motor datetime gotcha).
    """
    if earlier is None or later is None:
        return None

    earlier_utc = _ensure_utc(earlier)
    later_utc = _ensure_utc(later)

    delta = (later_utc - earlier_utc).total_seconds()
    # Clamp to zero – negative values could arise from clock skew and
    # are meaningless for latency analysis.
    return max(0.0, delta)
