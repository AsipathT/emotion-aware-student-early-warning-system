"""
Baseline models and input builders for Component 2:
- MajorityBaseline: Most frequent class predictor.
- rule_predict: Blackboard-like threshold rule on raw click ratio.
- build_rule_inputs: Weekly raw clicks and prior mean extractor.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.config import KEYS


class MajorityBaseline:
    """Baseline classifier predicting the most frequent class observed in training."""

    def __init__(self) -> None:
        self.majority_class_: Optional[str] = None

    def fit(self, y: Any) -> "MajorityBaseline":
        """Fits baseline by storing the most frequent class from y."""
        s = pd.Series(y)
        modes = s.mode()
        if len(modes) > 0:
            self.majority_class_ = str(modes.iloc[0])
        else:
            self.majority_class_ = "stable"
        return self

    def predict(self, n_or_X: Union[int, Any]) -> np.ndarray:
        """Returns the majority class repeated n times or len(X) times."""
        if isinstance(n_or_X, (int, np.integer)):
            n = int(n_or_X)
        else:
            n = len(n_or_X)
        return np.full(n, self.majority_class_, dtype=object)


def rule_predict(clicks_t: Any, prior_mean: Any) -> Union[str, np.ndarray]:
    """
    Fixed heuristic baseline (Blackboard-like) classifying trajectory by click ratio:
      ratio = clicks_t / prior_mean if prior_mean > 0 else 1.0
      ratio < 0.8 -> 'declining'
      ratio > 1.2 -> 'improving'
      else 'stable'
    Never predicts 'volatile'.
    """
    c = np.asarray(clicks_t, dtype=float)
    p = np.asarray(prior_mean, dtype=float)
    is_scalar = (c.ndim == 0 and p.ndim == 0)

    # Compute ratio vectorized
    ratio = np.where(p > 0, c / np.where(p > 0, p, 1.0), 1.0)

    preds = np.full(ratio.shape, "stable", dtype=object)
    preds[ratio < 0.8] = "declining"
    preds[ratio > 1.2] = "improving"

    if is_scalar:
        return str(preds.item())
    return preds


def build_rule_inputs(dense: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs raw clicks_t and prior_mean (weeks 0..t-1) for non-dormant label rows.
    """
    non_dorm = labels.loc[labels["label"] != "dormant"].copy().reset_index(drop=True)
    all_cols = KEYS + ["week", "label", "clicks_t", "prior_mean"]
    if non_dorm.empty:
        return pd.DataFrame(columns=all_cols)

    n_rows = len(non_dorm)
    clicks_t = np.empty(n_rows, dtype=float)
    prior_mean = np.empty(n_rows, dtype=float)

    label_groups = non_dorm.groupby(KEYS, sort=False).indices
    dense_groups = dense.groupby(KEYS, sort=False).indices

    clicks_all = dense["clicks"].to_numpy(dtype=float)
    dense_weeks = dense["week"].to_numpy(dtype=int)
    label_weeks = non_dorm["week"].to_numpy(dtype=int)

    for group_key, l_idx in label_groups.items():
        if group_key not in dense_groups:
            clicks_t[l_idx] = np.nan
            prior_mean[l_idx] = np.nan
            continue

        d_idx = dense_groups[group_key]
        grp_w = dense_weeks[d_idx]
        grp_c = clicks_all[d_idx]

        max_w = int(grp_w.max()) if len(grp_w) > 0 else 0
        if len(grp_w) == max_w + 1 and grp_w[0] == 0 and grp_w[-1] == max_w:
            c_grid = grp_c
        else:
            c_grid = np.zeros(max_w + 1, dtype=float)
            c_grid[grp_w] = grp_c

        c_cum = np.cumsum(c_grid)
        t_vals = label_weeks[l_idx]

        clicks_t[l_idx] = c_grid[t_vals]
        prior_sum = np.where(t_vals > 0, c_cum[np.maximum(0, t_vals - 1)], 0.0)
        prior_mean[l_idx] = np.where(t_vals > 0, prior_sum / np.maximum(1, t_vals), 0.0)

    result_dict: Dict[str, Any] = {
        KEYS[0]: non_dorm[KEYS[0]],
        KEYS[1]: non_dorm[KEYS[1]],
        KEYS[2]: non_dorm[KEYS[2]],
        "week": label_weeks,
        "label": non_dorm["label"],
        "clicks_t": clicks_t,
        "prior_mean": prior_mean,
    }

    return pd.DataFrame(result_dict)[all_cols]
