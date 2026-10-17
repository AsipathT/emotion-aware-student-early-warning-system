"""
Weekly clickstream and submission aggregation routines for Component 2.
"""

from pathlib import Path
from typing import List
import numpy as np
import pandas as pd

from src.config import KEYS


def load_weekly_clicks(oulad_dir: Path) -> pd.DataFrame:
    """
    Streams and aggregates studentVle.csv into weekly clicks and active day counts.
    Filters date >= 0 (pre-course interactions are excluded).
    """
    vle_path = Path(oulad_dir) / "studentVle.csv"
    chunk_size = 1_000_000
    chunk_aggs: List[pd.DataFrame] = []

    vle_chunks = pd.read_csv(
        vle_path,
        usecols=["code_module", "code_presentation", "id_student", "date", "sum_click"],
        dtype={"id_student": "int32", "date": "int16", "sum_click": "int32"},
        chunksize=chunk_size,
    )

    for chunk in vle_chunks:
        valid_chunk = chunk[chunk["date"] >= 0]
        if not valid_chunk.empty:
            c_agg = valid_chunk.groupby(KEYS + ["date"], as_index=False)["sum_click"].sum()
            chunk_aggs.append(c_agg)

    if not chunk_aggs:
        return pd.DataFrame(columns=KEYS + ["week", "clicks", "active_days"])

    all_clicks = pd.concat(chunk_aggs, ignore_index=True)
    daily = all_clicks.groupby(KEYS + ["date"], as_index=False)["sum_click"].sum()

    daily["week"] = (daily["date"] // 7).astype(int)

    weekly = daily.groupby(KEYS + ["week"], as_index=False).agg(
        clicks=("sum_click", "sum"),
        active_days=("date", "count"),
    )
    weekly["clicks"] = weekly["clicks"].astype(int)
    weekly["active_days"] = weekly["active_days"].astype(int)
    weekly["week"] = weekly["week"].astype(int)

    return weekly


def load_weekly_submissions(oulad_dir: Path) -> pd.DataFrame:
    """
    Loads and aggregates assignment submissions into weekly counts and average delays.
    Filters out Exams and items without a due date.
    """
    assessments_path = Path(oulad_dir) / "assessments.csv"
    sub_path = Path(oulad_dir) / "studentAssessment.csv"

    assessments = pd.read_csv(assessments_path)
    student_assessment = pd.read_csv(sub_path)

    merged = pd.merge(
        student_assessment,
        assessments,
        on="id_assessment",
        how="inner",
    )

    # Filter out Exams and assessments with missing due date
    merged = merged[merged["assessment_type"] != "Exam"]
    merged = merged[merged["date"].notna()]

    # Filter out submissions with missing or negative submission date
    merged = merged[merged["date_submitted"].notna()]
    merged["date_submitted"] = merged["date_submitted"].astype(float)
    merged["date"] = merged["date"].astype(float)

    merged["week"] = (merged["date_submitted"] // 7).astype(int)
    merged = merged[merged["week"] >= 0]

    if merged.empty:
        return pd.DataFrame(columns=KEYS + ["week", "submissions_count", "avg_delay_hours"])

    # Compute delay_hours: 0.0 if banked else (date_submitted - date) * 24.0
    is_banked_mask = (merged["is_banked"] == 1) | (merged["is_banked"] is True)
    delays = (merged["date_submitted"] - merged["date"]) * 24.0
    merged["delay_hours"] = np.where(is_banked_mask, 0.0, delays)

    weekly_subs = merged.groupby(KEYS + ["week"], as_index=False).agg(
        submissions_count=("delay_hours", "count"),
        avg_delay_hours=("delay_hours", "mean"),
    )
    weekly_subs["submissions_count"] = weekly_subs["submissions_count"].astype(int)
    weekly_subs["avg_delay_hours"] = weekly_subs["avg_delay_hours"].astype(float)
    weekly_subs["week"] = weekly_subs["week"].astype(int)

    return weekly_subs


def build_dense_weekly(
    enrol: pd.DataFrame, clicks: pd.DataFrame, subs: pd.DataFrame
) -> pd.DataFrame:
    """
    Constructs a contiguous weekly grid per non-excluded student up to end_week.
    Fills weeks with zero interactions and zero-censors after end_week.
    """
    target_cols = KEYS + [
        "week",
        "clicks",
        "active_days",
        "submissions_count",
        "avg_delay_hours",
        "final_result",
    ]

    valid_enrol = enrol.loc[~enrol["excluded"]].copy()
    if valid_enrol.empty:
        return pd.DataFrame(columns=target_cols)

    num_weeks = (valid_enrol["end_week"] + 1).astype(int)
    repeated = valid_enrol.loc[valid_enrol.index.repeat(num_weeks)].copy()
    repeated["week"] = repeated.groupby(level=0).cumcount().astype(int)

    dense = pd.merge(repeated, clicks, on=KEYS + ["week"], how="left")
    dense = pd.merge(dense, subs, on=KEYS + ["week"], how="left")

    dense["clicks"] = dense["clicks"].fillna(0).astype(int)
    dense["active_days"] = dense["active_days"].fillna(0).astype(int)
    dense["submissions_count"] = dense["submissions_count"].fillna(0).astype(int)
    dense["avg_delay_hours"] = dense["avg_delay_hours"].fillna(0.0).astype(float)

    dense = dense.sort_values(by=KEYS + ["week"]).reset_index(drop=True)
    return dense[target_cols].copy()
