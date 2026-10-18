"""
Scale-free deployment feature transformations for Component 2.
"""

from typing import List
import pandas as pd
from src.config import KEYS

DEPLOY_FEATURES: List[str] = [
    "c_lag0",
    "c_lag1",
    "c_lag2",
    "c_lag3",
    "c_lag4",
    "c_lag5",
    "e_sd6",
    "e_slope4",
    "e_recent_diff",
    "zero_weeks6",
    "zero_run",
    "week_t",
    "subs_sum6",
    "delay_mean6",
]


def to_deploy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms causal features into scale-free deployment features:
      - c_lagJ = e_lagJ - e_mean6 for J=0..5 (scale-free centered log-clicks).
      - Drops raw level and activity-day features.
      - Keeps other listed DEPLOY_FEATURES and any existing KEYS/week/label columns.
    """
    out = pd.DataFrame(index=df.index)
    passthrough = [c for c in KEYS + ["week", "label"] if c in df.columns]
    for c in passthrough:
        out[c] = df[c]

    for j in range(6):
        out[f"c_lag{j}"] = df[f"e_lag{j}"] - df["e_mean6"]

    other_features = [
        "e_sd6",
        "e_slope4",
        "e_recent_diff",
        "zero_weeks6",
        "zero_run",
        "week_t",
        "subs_sum6",
        "delay_mean6",
    ]
    for col in other_features:
        out[col] = df[col]

    return out[passthrough + DEPLOY_FEATURES]
