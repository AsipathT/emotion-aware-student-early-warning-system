"""
backend/app/pipeline/clock.py

Injectable clock mechanism for the pipeline orchestrator.
Allows automated tests to time-travel deterministically without sleeping.
Supports both fixed datetime instances and dynamic provider functions.
"""

from datetime import datetime, timezone
from typing import Callable, Optional, Union

_custom_clock: Optional[Callable[[], datetime]] = None


def get_clock() -> datetime:
    """Returns the current UTC datetime from the injectable clock, or real UTC now."""
    if _custom_clock is not None:
        dt = _custom_clock()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def set_clock(val: Optional[Union[datetime, Callable[[], datetime]]]) -> None:
    """Sets a custom clock provider function or fixed datetime (for testing)."""
    global _custom_clock
    if isinstance(val, datetime):
        _custom_clock = lambda: val
    else:
        _custom_clock = val


def reset_clock() -> None:
    """Resets clock to standard system UTC now."""
    global _custom_clock
    _custom_clock = None
