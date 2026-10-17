"""
Enrolment table construction and censoring logic for Component 2.
"""

from typing import List
import numpy as np
import pandas as pd

from src.config import KEYS


def build_enrolment_table(
    info: pd.DataFrame, reg: pd.DataFrame, courses: pd.DataFrame
) -> pd.DataFrame:
    """
    Builds enrolment table by joining studentInfo, studentRegistration, and courses.
    Determines study span (last_week, end_week) and identifies excluded student records.
    """
    merged = pd.merge(info, reg, on=KEYS, how="left")
    merged = pd.merge(merged, courses, on=["code_module", "code_presentation"], how="left")

    last_week_series = (merged["module_presentation_length"].astype(int) + 6) // 7 - 1

    end_week_series = last_week_series.copy()
    excluded_series = pd.Series(False, index=merged.index, dtype=bool)
    exclude_reason_series = pd.Series("", index=merged.index, dtype=object)

    is_withdrawn = merged["final_result"].astype(str) == "Withdrawn"

    # Case 1: Withdrawn with missing date_unregistration
    mask_no_date = is_withdrawn & merged["date_unregistration"].isna()
    end_week_series.loc[mask_no_date] = -1
    excluded_series.loc[mask_no_date] = True
    exclude_reason_series.loc[mask_no_date] = "withdrawn_no_unreg_date"

    # Case 2: Withdrawn with negative date_unregistration
    mask_neg_date = (
        is_withdrawn
        & merged["date_unregistration"].notna()
        & (merged["date_unregistration"] < 0)
    )
    end_week_series.loc[mask_neg_date] = -1
    excluded_series.loc[mask_neg_date] = True
    exclude_reason_series.loc[mask_neg_date] = "unreg_before_start"

    # Case 3: Withdrawn with valid date_unregistration >= 0
    mask_valid_withdrawn = (
        is_withdrawn
        & merged["date_unregistration"].notna()
        & (merged["date_unregistration"] >= 0)
    )
    if mask_valid_withdrawn.any():
        unreg_weeks = (merged.loc[mask_valid_withdrawn, "date_unregistration"] // 7).astype(int)
        lw = last_week_series.loc[mask_valid_withdrawn]
        end_week_series.loc[mask_valid_withdrawn] = np.minimum(unreg_weeks, lw)

    # Case 4: Any record where end_week < 0 and not already excluded
    mask_end_neg = (~excluded_series) & (end_week_series < 0)
    end_week_series.loc[mask_end_neg] = -1
    excluded_series.loc[mask_end_neg] = True
    exclude_reason_series.loc[mask_end_neg] = "end_before_start"

    result = merged.copy()
    result["last_week"] = last_week_series.astype(int)
    result["end_week"] = end_week_series.astype(int)
    result["excluded"] = excluded_series.astype(bool)
    result["exclude_reason"] = exclude_reason_series.astype(str)

    target_cols: List[str] = KEYS + [
        "final_result",
        "date_unregistration",
        "module_presentation_length",
        "last_week",
        "end_week",
        "excluded",
        "exclude_reason",
    ]
    return result[target_cols].copy()
