"""
Causal dormancy rule detection for inference in Component 2.
"""

from typing import List, Optional
from src.config import DORMANT_ZERO_WEEKS


def causal_dormancy(clicks_upto_t: List[float]) -> Optional[str]:
    """
    Checks for causal dormancy over weekly clicks from week 0 up to t (last element is week t).
    Returns:
      - None: if fewer than DORMANT_ZERO_WEEKS weeks or not all of the last DORMANT_ZERO_WEEKS weeks are 0.
      - "no_activity_7w": if all of the last DORMANT_ZERO_WEEKS weeks are 0 and any earlier week had click > 0.
      - "never_active": if all of the last DORMANT_ZERO_WEEKS weeks are 0 and no earlier week had click > 0.
    """
    if len(clicks_upto_t) < DORMANT_ZERO_WEEKS:
        return None

    last_window = clicks_upto_t[-DORMANT_ZERO_WEEKS:]
    if not all(c == 0 for c in last_window):
        return None

    earlier = clicks_upto_t[:-DORMANT_ZERO_WEEKS]
    if any(c > 0 for c in earlier):
        return "no_activity_7w"
    return "never_active"
