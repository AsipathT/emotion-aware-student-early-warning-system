"""
Train, validation, and test split definitions for Component 2.
Implements presentation-temporal splits with cross-presentation student deduplication.
"""

from typing import Any, Dict, List
import pandas as pd

PRESENTATION_ORDER: List[str] = ["2013B", "2013J", "2014B", "2014J"]


def make_splits(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Partitions the dataset into train, val, and test splits:
      - train: presentations 2013B + 2013J (no removal)
      - val:   2014B rows whose id_student does NOT appear in 2013B or 2013J
      - test:  2014J rows whose id_student does NOT appear in 2013B, 2013J or 2014B
    """
    train_mask = df["code_presentation"].isin(["2013B", "2013J"])
    train_students = set(df.loc[train_mask, "id_student"].unique())

    val_pres_mask = df["code_presentation"] == "2014B"
    val_mask = val_pres_mask & (~df["id_student"].isin(train_students))

    prior_students = set(
        df.loc[df["code_presentation"].isin(["2013B", "2013J", "2014B"]), "id_student"].unique()
    )
    test_pres_mask = df["code_presentation"] == "2014J"
    test_mask = test_pres_mask & (~df["id_student"].isin(prior_students))

    return {
        "train": df.loc[train_mask].copy(),
        "val": df.loc[val_mask].copy(),
        "test": df.loc[test_mask].copy(),
    }


def split_report(df: pd.DataFrame, splits: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Summarizes windows and distinct students per split, plus rows removed by overlap rules.
    """
    val_pres_count = int((df["code_presentation"] == "2014B").sum())
    val_kept_count = len(splits["val"])
    removed_val = val_pres_count - val_kept_count

    test_pres_count = int((df["code_presentation"] == "2014J").sum())
    test_kept_count = len(splits["test"])
    removed_test = test_pres_count - test_kept_count

    return {
        "train": {
            "windows": len(splits["train"]),
            "distinct_students": int(splits["train"]["id_student"].nunique())
            if len(splits["train"]) > 0
            else 0,
        },
        "val": {
            "windows": len(splits["val"]),
            "distinct_students": int(splits["val"]["id_student"].nunique())
            if len(splits["val"]) > 0
            else 0,
        },
        "test": {
            "windows": len(splits["test"]),
            "distinct_students": int(splits["test"]["id_student"].nunique())
            if len(splits["test"]) > 0
            else 0,
        },
        "removed_val": removed_val,
        "removed_test": removed_test,
    }
