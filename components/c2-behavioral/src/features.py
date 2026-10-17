"""
Feature extraction routines for Component 2 (Behavioral Engagement Trajectory).
Includes causal features (weeks <= t) and static snapshot features (cumulative up to t).
"""

from typing import Any, Dict, List, Tuple
import warnings
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from src.config import KEYS

CAUSAL_FEATURE_NAMES: List[str] = [
    "e_lag0",
    "e_lag1",
    "e_lag2",
    "e_lag3",
    "e_lag4",
    "e_lag5",
    "e_mean6",
    "e_sd6",
    "e_slope4",
    "e_recent_diff",
    "zero_weeks6",
    "zero_run",
    "ad_lag0",
    "ad_mean3",
    "subs_sum6",
    "delay_mean6",
    "week_t",
]

STATIC_FEATURE_NAMES: List[str] = [
    "cum_log_clicks",
    "cum_active_days",
    "cum_submissions",
    "cum_delay_mean",
    "week_t",
]


def build_causal_features(dense: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs causal features for non-dormant label rows using weeks <= t only.
    Vectorized per group using numpy sliding windows and lags.
    """
    non_dorm = labels.loc[labels["label"] != "dormant"].copy().reset_index(drop=True)
    all_cols = KEYS + ["week", "label"] + CAUSAL_FEATURE_NAMES
    if non_dorm.empty:
        return pd.DataFrame(columns=all_cols)

    n_rows = len(non_dorm)
    e_lags_all = np.empty((n_rows, 6), dtype=float)
    a_lags_all = np.empty((n_rows, 6), dtype=float)
    s_lags_all = np.empty((n_rows, 6), dtype=float)
    d_lags_all = np.empty((n_rows, 6), dtype=float)

    label_groups = non_dorm.groupby(KEYS, sort=False).indices
    dense_groups = dense.groupby(KEYS, sort=False).indices

    clicks_all = dense["clicks"].to_numpy(dtype=float)
    active_all = dense["active_days"].to_numpy(dtype=float)
    subs_all = dense["submissions_count"].to_numpy(dtype=float)
    delay_all = dense["avg_delay_hours"].to_numpy(dtype=float)
    delay_masked = np.where(subs_all == 0, np.nan, delay_all)

    dense_weeks = dense["week"].to_numpy(dtype=int)
    label_weeks = non_dorm["week"].to_numpy(dtype=int)

    for group_key, l_idx in label_groups.items():
        if group_key not in dense_groups:
            e_lags_all[l_idx] = np.nan
            a_lags_all[l_idx] = np.nan
            s_lags_all[l_idx] = np.nan
            d_lags_all[l_idx] = np.nan
            continue

        d_idx = dense_groups[group_key]
        grp_w = dense_weeks[d_idx]
        grp_c = clicks_all[d_idx]
        grp_a = active_all[d_idx]
        grp_s = subs_all[d_idx]
        grp_d = delay_masked[d_idx]

        max_w = int(grp_w.max()) if len(grp_w) > 0 else 0
        if len(grp_w) == max_w + 1 and grp_w[0] == 0 and grp_w[-1] == max_w:
            c_grid = grp_c
            a_grid = grp_a
            s_grid = grp_s
            d_grid = grp_d
        else:
            c_grid = np.zeros(max_w + 1, dtype=float)
            c_grid[grp_w] = grp_c
            a_grid = np.zeros(max_w + 1, dtype=float)
            a_grid[grp_w] = grp_a
            s_grid = np.zeros(max_w + 1, dtype=float)
            s_grid[grp_w] = grp_s
            d_grid = np.full(max_w + 1, np.nan, dtype=float)
            d_grid[grp_w] = grp_d

        e = np.log1p(c_grid)
        pad_e = np.pad(e, (5, 0), constant_values=np.nan)
        w_e = sliding_window_view(pad_e, 6)[:, ::-1]

        pad_a = np.pad(a_grid, (5, 0), constant_values=np.nan)
        w_a = sliding_window_view(pad_a, 6)[:, ::-1]

        pad_s = np.pad(s_grid, (5, 0), constant_values=np.nan)
        w_s = sliding_window_view(pad_s, 6)[:, ::-1]

        pad_d = np.pad(d_grid, (5, 0), constant_values=np.nan)
        w_d = sliding_window_view(pad_d, 6)[:, ::-1]

        t_vals = label_weeks[l_idx]
        e_lags_all[l_idx] = w_e[t_vals]
        a_lags_all[l_idx] = w_a[t_vals]
        s_lags_all[l_idx] = w_s[t_vals]
        d_lags_all[l_idx] = w_d[t_vals]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        e_mean6 = np.nanmean(e_lags_all, axis=1)
        e_sd6 = np.nanstd(e_lags_all, axis=1, ddof=0)
        e_slope4 = (
            -1.5 * e_lags_all[:, 3]
            - 0.5 * e_lags_all[:, 2]
            + 0.5 * e_lags_all[:, 1]
            + 1.5 * e_lags_all[:, 0]
        ) / 5.0
        mean_02 = np.nanmean(e_lags_all[:, 0:3], axis=1)
        mean_35 = np.nanmean(e_lags_all[:, 3:6], axis=1)
        e_recent_diff = mean_02 - mean_35
        zero_weeks6 = (e_lags_all == 0.0).sum(axis=1)

        zero_run = np.zeros(n_rows, dtype=int)
        active_zeros = np.ones(n_rows, dtype=bool)
        for j in range(6):
            active_zeros = active_zeros & (e_lags_all[:, j] == 0.0)
            zero_run += active_zeros.astype(int)

        ad_lag0 = a_lags_all[:, 0]
        ad_mean3 = np.nanmean(a_lags_all[:, 0:3], axis=1)
        subs_sum6 = np.nansum(s_lags_all, axis=1)
        delay_mean6 = np.nanmean(d_lags_all, axis=1)

    result_dict: Dict[str, Any] = {
        KEYS[0]: non_dorm[KEYS[0]],
        KEYS[1]: non_dorm[KEYS[1]],
        KEYS[2]: non_dorm[KEYS[2]],
        "week": label_weeks,
        "label": non_dorm["label"],
        "e_lag0": e_lags_all[:, 0],
        "e_lag1": e_lags_all[:, 1],
        "e_lag2": e_lags_all[:, 2],
        "e_lag3": e_lags_all[:, 3],
        "e_lag4": e_lags_all[:, 4],
        "e_lag5": e_lags_all[:, 5],
        "e_mean6": e_mean6,
        "e_sd6": e_sd6,
        "e_slope4": e_slope4,
        "e_recent_diff": e_recent_diff,
        "zero_weeks6": zero_weeks6,
        "zero_run": zero_run,
        "ad_lag0": ad_lag0,
        "ad_mean3": ad_mean3,
        "subs_sum6": subs_sum6,
        "delay_mean6": delay_mean6,
        "week_t": label_weeks,
    }

    return pd.DataFrame(result_dict)[all_cols]


def build_static_features(dense: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs cumulative static features (weeks 0 up to t) for non-dormant label rows.
    """
    non_dorm = labels.loc[labels["label"] != "dormant"].copy().reset_index(drop=True)
    all_cols = KEYS + ["week", "label"] + STATIC_FEATURE_NAMES
    if non_dorm.empty:
        return pd.DataFrame(columns=all_cols)

    n_rows = len(non_dorm)
    cum_log_clicks = np.empty(n_rows, dtype=float)
    cum_active_days = np.empty(n_rows, dtype=float)
    cum_subs = np.empty(n_rows, dtype=float)
    cum_delay_mean = np.empty(n_rows, dtype=float)

    label_groups = non_dorm.groupby(KEYS, sort=False).indices
    dense_groups = dense.groupby(KEYS, sort=False).indices

    clicks_all = dense["clicks"].to_numpy(dtype=float)
    active_all = dense["active_days"].to_numpy(dtype=float)
    subs_all = dense["submissions_count"].to_numpy(dtype=float)
    delay_all = dense["avg_delay_hours"].to_numpy(dtype=float)

    dense_weeks = dense["week"].to_numpy(dtype=int)
    label_weeks = non_dorm["week"].to_numpy(dtype=int)

    for group_key, l_idx in label_groups.items():
        if group_key not in dense_groups:
            cum_log_clicks[l_idx] = np.nan
            cum_active_days[l_idx] = np.nan
            cum_subs[l_idx] = np.nan
            cum_delay_mean[l_idx] = np.nan
            continue

        d_idx = dense_groups[group_key]
        grp_w = dense_weeks[d_idx]
        grp_c = clicks_all[d_idx]
        grp_a = active_all[d_idx]
        grp_s = subs_all[d_idx]
        grp_d = delay_all[d_idx]

        max_w = int(grp_w.max()) if len(grp_w) > 0 else 0
        if len(grp_w) == max_w + 1 and grp_w[0] == 0 and grp_w[-1] == max_w:
            c_grid = grp_c
            a_grid = grp_a
            s_grid = grp_s
            d_grid = grp_d
        else:
            c_grid = np.zeros(max_w + 1, dtype=float)
            c_grid[grp_w] = grp_c
            a_grid = np.zeros(max_w + 1, dtype=float)
            a_grid[grp_w] = grp_a
            s_grid = np.zeros(max_w + 1, dtype=float)
            s_grid[grp_w] = grp_s
            d_grid = np.zeros(max_w + 1, dtype=float)
            d_grid[grp_w] = grp_d

        c_cum = np.cumsum(c_grid)
        a_cum = np.cumsum(a_grid)
        s_cum = np.cumsum(s_grid)
        tot_delay_cum = np.cumsum(d_grid * s_grid)

        t_vals = label_weeks[l_idx]
        cum_log_clicks[l_idx] = np.log1p(c_cum[t_vals])
        cum_active_days[l_idx] = a_cum[t_vals]
        s_vals = s_cum[t_vals]
        cum_subs[l_idx] = s_vals
        cum_delay_mean[l_idx] = np.where(
            s_vals > 0, tot_delay_cum[t_vals] / np.where(s_vals > 0, s_vals, 1.0), np.nan
        )

    result_dict: Dict[str, Any] = {
        KEYS[0]: non_dorm[KEYS[0]],
        KEYS[1]: non_dorm[KEYS[1]],
        KEYS[2]: non_dorm[KEYS[2]],
        "week": label_weeks,
        "label": non_dorm["label"],
        "cum_log_clicks": cum_log_clicks,
        "cum_active_days": cum_active_days,
        "cum_submissions": cum_subs,
        "cum_delay_mean": cum_delay_mean,
        "week_t": label_weeks,
    }

    return pd.DataFrame(result_dict)[all_cols]
