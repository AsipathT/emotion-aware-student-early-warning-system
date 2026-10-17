"""
Engagement trajectory labeling and sliding-window statistics for Component 2.
"""

from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from src.config import (
    KEYS,
    MIN_T,
    RESID_SD_HI,
    S_FLAT,
    S_TREND,
)


def window_stats(e: np.ndarray) -> Tuple[float, float]:
    """
    Computes linear slope and residual standard deviation for a 7-week log-engagement window.
    """
    x = np.arange(-3, 4, dtype=float)
    slope = float((x * e).sum() / (x ** 2).sum())
    resid = e - e.mean() - slope * x
    resid_sd = float(np.std(resid))
    return slope, resid_sd


def label_from_stats(slope: float, resid_sd: float) -> str:
    """
    Classifies engagement trajectory from window slope and residual standard deviation
    following the priority order in label_spec.md:
    1. volatile  : resid_sd >= RESID_SD_HI and abs(slope) < S_FLAT
    2. declining : slope <= -S_TREND
    3. improving : slope >= S_TREND
    4. stable    : otherwise
    """
    if resid_sd >= RESID_SD_HI and abs(slope) < S_FLAT:
        return "volatile"
    elif slope <= -S_TREND:
        return "declining"
    elif slope >= S_TREND:
        return "improving"
    else:
        return "stable"


def compute_labels(dense: pd.DataFrame) -> pd.DataFrame:
    """
    Computes 7-week centered engagement trajectory labels for each student.
    Identifies dormant windows and applies the C2 rule-based label hierarchy.
    """
    output_cols = KEYS + [
        "week",
        "slope",
        "resid_sd",
        "dormant",
        "label",
        "final_result",
    ]
    if dense.empty:
        return pd.DataFrame(columns=output_cols)

    sorted_dense = dense.sort_values(by=KEYS + ["week"]).reset_index(drop=True)

    records: List[Dict[str, Any]] = []
    x = np.arange(-3, 4, dtype=float)
    x_sq_sum = 28.0

    for group_key, grp in sorted_dense.groupby(KEYS, sort=False):
        n_rows = len(grp)
        if n_rows < 7:
            continue

        clicks_arr = grp["clicks"].to_numpy(dtype=float)
        e_arr = np.log1p(clicks_arr)
        final_result_val = grp["final_result"].iloc[0]

        windows_e = np.lib.stride_tricks.sliding_window_view(e_arr, 7)
        windows_clicks = np.lib.stride_tricks.sliding_window_view(clicks_arr, 7)

        slopes = (windows_e * x).sum(axis=1) / x_sq_sum
        means = windows_e.mean(axis=1, keepdims=True)
        resids = windows_e - means - slopes[:, None] * x
        resid_sds = np.std(resids, axis=1)
        dormant_flags = (windows_clicks.sum(axis=1) == 0)

        week_vals = grp["week"].iloc[3 : n_rows - 3].to_numpy()

        k0 = group_key[0] if isinstance(group_key, tuple) else group_key
        k1 = group_key[1] if isinstance(group_key, tuple) else grp[KEYS[1]].iloc[0]
        k2 = group_key[2] if isinstance(group_key, tuple) else grp[KEYS[2]].iloc[0]

        for idx in range(len(slopes)):
            s = float(slopes[idx])
            sd = float(resid_sds[idx])
            is_dormant = bool(dormant_flags[idx])
            lbl = "dormant" if is_dormant else label_from_stats(s, sd)

            rec = {
                KEYS[0]: k0,
                KEYS[1]: k1,
                KEYS[2]: k2,
                "week": int(week_vals[idx]),
                "slope": s,
                "resid_sd": sd,
                "dormant": is_dormant,
                "label": lbl,
                "final_result": final_result_val,
            }
            records.append(rec)

    if not records:
        return pd.DataFrame(columns=output_cols)

    return pd.DataFrame(records)[output_cols]
