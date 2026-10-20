"""
Online trajectory inference for single student histories.
Supports cold start handling, causal dormancy rules, and model predictions.
"""

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from src.config import DORMANT_RULE_CONFIDENCE, INFER_MIN_WEEKS
from src.deploy_features import to_deploy
from src.dormant import causal_dormancy
from src.features import build_causal_features
from src.indicators import contributing_indicators, low_activity_vs_history



def predict_trajectory(
    history: pd.DataFrame, bundle: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Predicts trajectory label, confidence, and contributing indicators for a single student history.
    history: columns [week, clicks, submissions_count, avg_delay_hours], exactly 0..t contiguous.
    Returns:
      - None if len(history) < INFER_MIN_WEEKS
      - Rule-based dormant dict if causal_dormancy triggers
      - Model prediction dict otherwise
    """
    if "week" not in history.columns:
        raise ValueError("history DataFrame must contain 'week' column.")

    weeks = history["week"].to_numpy()
    n = len(weeks)
    if not np.array_equal(weeks, np.arange(n)):
        raise ValueError(
            f"History weeks must be exactly contiguous 0..t without gaps or duplicates, got {weeks.tolist()}"
        )

    # 1. Cold start / insufficient history check
    if n < INFER_MIN_WEEKS:
        return None

    # 2. Causal dormancy check
    clicks_list = [float(c) for c in history["clicks"]]
    r = causal_dormancy(clicks_list)
    if r is not None:
        return {
            "trajectory_label": "declining",
            "confidence": DORMANT_RULE_CONFIDENCE,
            "contributing_indicators": [r],
        }

    # 3. Model inference
    if bundle is None:
        raise ValueError("bundle dictionary is required for model inference.")

    t = int(weeks[-1])
    dense_df = pd.DataFrame(
        {
            "code_module": ["x"] * n,
            "code_presentation": ["x"] * n,
            "id_student": [0] * n,
            "week": weeks.astype(int),
            "clicks": history["clicks"].to_numpy(dtype=float),
            "active_days": np.zeros(n, dtype=float),
            "submissions_count": history["submissions_count"].to_numpy(dtype=float),
            "avg_delay_hours": history["avg_delay_hours"].to_numpy(dtype=float),
            "final_result": [""] * n,
        }
    )

    labels_df = pd.DataFrame(
        {
            "code_module": ["x"],
            "code_presentation": ["x"],
            "id_student": [0],
            "week": [t],
            "slope": [0.0],
            "resid_sd": [0.0],
            "dormant": [False],
            "label": ["stable"],
            "final_result": [""],
        }
    )

    raw_feat = build_causal_features(dense_df, labels_df)
    deploy_feat = to_deploy(raw_feat)

    features = bundle["features"]
    X = deploy_feat[features]
    model = bundle["model"]

    proba = model.predict_proba(X)[0]
    classes = model.classes_
    best_idx = int(np.argmax(proba))
    label = str(classes[best_idx])
    confidence = float(proba[best_idx])

    raw_row_dict = raw_feat.iloc[0].to_dict()
    indicators = contributing_indicators(raw_row_dict, label)

    raw_clicks = [float(c) for c in history["clicks"]]
    if low_activity_vs_history(raw_clicks):
        if "steady_activity" in indicators:
            indicators.remove("steady_activity")
        if "low_activity_vs_own_history" not in indicators:
            indicators.append("low_activity_vs_own_history")
        indicators = indicators[:10]

    # 4. Return result
    return {
        "trajectory_label": label,
        "confidence": confidence,
        "contributing_indicators": indicators,
    }

