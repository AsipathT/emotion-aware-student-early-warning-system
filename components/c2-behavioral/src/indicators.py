"""
Rule-based contributing indicator extraction for trajectory explanation.
"""

from typing import Any, Dict, List
import pandas as pd

from src.config import INDICATOR_DIFF, LATE_DELAY_HOURS, RESID_SD_HI, S_TREND


def contributing_indicators(row: Dict[str, Any], label: str) -> List[str]:
    """
    Identifies human-readable contributing indicators from raw causal feature values.
    Applies fixed priority rules in order. NaN-safe, maximum 10 items, no duplicates.
    Returns ['steady_activity'] if no indicator triggers.
    """
    indicators: List[str] = []

    # 1. Slope trend
    e_slope4 = row.get("e_slope4")
    if e_slope4 is not None and not pd.isna(e_slope4):
        if e_slope4 <= -S_TREND:
            indicators.append("clicks_declining_trend")
        elif e_slope4 >= S_TREND:
            indicators.append("clicks_rising_trend")

    # 2. Recent difference
    e_recent_diff = row.get("e_recent_diff")
    if e_recent_diff is not None and not pd.isna(e_recent_diff):
        if e_recent_diff <= -INDICATOR_DIFF:
            indicators.append("recent_activity_drop")
        elif e_recent_diff >= INDICATOR_DIFF:
            indicators.append("recent_activity_rise")

    # 3. Variability
    e_sd6 = row.get("e_sd6")
    if e_sd6 is not None and not pd.isna(e_sd6):
        if e_sd6 >= RESID_SD_HI:
            indicators.append("high_weekly_variability")

    # 4. Inactivity streak vs frequent zero weeks
    zero_run = row.get("zero_run")
    zero_weeks6 = row.get("zero_weeks6")
    if zero_run is not None and not pd.isna(zero_run) and zero_run >= 2:
        indicators.append("inactive_streak")
    elif zero_weeks6 is not None and not pd.isna(zero_weeks6) and zero_weeks6 >= 2:
        indicators.append("frequent_zero_weeks")

    # 5. Late submissions
    delay_mean6 = row.get("delay_mean6")
    if delay_mean6 is not None and not pd.isna(delay_mean6):
        if delay_mean6 > LATE_DELAY_HOURS:
            indicators.append("late_submissions")

    # Deduplicate while preserving order, cap at 10 items
    seen = set()
    deduped: List[str] = []
    for item in indicators:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
            if len(deduped) == 10:
                break

    if not deduped:
        return ["steady_activity"]

    return deduped
