"""
src/evaluation.py

Comprehensive evaluation module for Component 1: Affective State Detection.
Handles:
1. Multi-label metric calculations (Precision, Recall, F1, ROC-AUC per class and macro).
2. Per-class threshold tuning on validation set only.
3. Multi-label confusion-style matrix calculation and figure generation.
4. Metric segmentation split by source (goemotions_proxy vs emotion4_proxy).
5. Saving structured metrics JSON and figures.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import json
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    multilabel_confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger("c1_evaluation")

DEFAULT_CLASSES = [
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
]


def tune_thresholds_on_val(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_names: List[str] = DEFAULT_CLASSES,
    grid: Optional[List[float]] = None,
) -> Dict[str, float]:
    """
    Tuning per-class decision thresholds exclusively on the validation set.
    Selects the threshold in grid that maximizes per-class F1 score.
    """
    if grid is None:
        grid = [round(x, 2) for x in np.arange(0.10, 0.95, 0.05)]

    best_thresholds: Dict[str, float] = {}
    for i, cls in enumerate(class_names):
        best_f1 = -1.0
        best_t = 0.50
        y_t = y_true[:, i]
        y_p = y_probs[:, i]

        if y_t.sum() == 0:
            best_thresholds[cls] = 0.50
            continue

        for t in grid:
            preds = (y_p >= t).astype(int)
            score = f1_score(y_t, preds, zero_division=0)
            if score > best_f1:
                best_f1 = score
                best_t = float(t)

        best_thresholds[cls] = best_t
        logger.info(f"Tuned threshold for {cls:22s}: {best_t:.2f} (val F1={best_f1:.4f})")

    return best_thresholds


def compute_multilabel_metrics(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    thresholds: Union[float, Dict[str, float]] = 0.50,
    class_names: List[str] = DEFAULT_CLASSES,
) -> Dict[str, any]:
    """
    Computes per-class and macro multi-label evaluation metrics:
    - Precision, Recall, F1, ROC-AUC
    - Overall Macro F1, Macro Precision, Macro Recall, Macro ROC-AUC
    """
    if isinstance(thresholds, (int, float)):
        thresh_dict = {cls: float(thresholds) for cls in class_names}
    else:
        thresh_dict = thresholds

    y_pred = np.zeros_like(y_true, dtype=int)
    for i, cls in enumerate(class_names):
        t = thresh_dict.get(cls, 0.50)
        y_pred[:, i] = (y_probs[:, i] >= t).astype(int)

    per_class_metrics: Dict[str, Dict[str, float]] = {}
    roc_aucs: List[float] = []

    for i, cls in enumerate(class_names):
        yt = y_true[:, i]
        yp = y_pred[:, i]
        yprob = y_probs[:, i]

        p = float(precision_score(yt, yp, zero_division=0))
        r = float(recall_score(yt, yp, zero_division=0))
        f = float(f1_score(yt, yp, zero_division=0))

        # Handle ROC-AUC when only one class is present
        if len(np.unique(yt)) > 1:
            auc = float(roc_auc_score(yt, yprob))
            roc_aucs.append(auc)
        else:
            auc = 0.50

        per_class_metrics[cls] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "roc_auc": round(auc, 4),
            "support": int(yt.sum()),
            "predicted_positives": int(yp.sum()),
            "applied_threshold": round(thresh_dict.get(cls, 0.50), 4),
        }

    macro_f1 = float(np.mean([m["f1"] for m in per_class_metrics.values()]))
    supported_f1s = [m["f1"] for m in per_class_metrics.values() if m["support"] > 0]
    macro_f1_supported = float(np.mean(supported_f1s)) if supported_f1s else 0.0
    macro_prec = float(np.mean([m["precision"] for m in per_class_metrics.values()]))
    macro_rec = float(np.mean([m["recall"] for m in per_class_metrics.values()]))
    macro_auc = float(np.mean(roc_aucs)) if roc_aucs else 0.50

    # Subset accuracy (exact match across all 5 classes)
    exact_match = float(accuracy_score(y_true, y_pred))

    return {
        "macro_metrics": {
            "macro_f1": round(macro_f1, 4),
            "macro_f1_supported_classes": round(macro_f1_supported, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "macro_roc_auc": round(macro_auc, 4),
            "exact_match_ratio": round(exact_match, 4),
            "zero_support_classes_excluded_from_supported_macro": bool(len(supported_f1s) < len(class_names)),
        },
        "per_class_metrics": per_class_metrics,
        "total_samples": int(len(y_true)),
    }


def compute_split_by_source_metrics(
    df: pd.DataFrame,
    y_probs: np.ndarray,
    thresholds: Dict[str, float],
    class_names: List[str] = DEFAULT_CLASSES,
) -> Dict[str, any]:
    """Computes full multi-label metrics segmented by data source (goemotions_proxy vs emotion4_proxy)."""
    source_results: Dict[str, any] = {}
    sources = df["source"].unique()

    for src in sources:
        idx = (df["source"] == src).values
        y_true_src = df.loc[idx, class_names].values.astype(int)
        y_probs_src = y_probs[idx]

        metrics = compute_multilabel_metrics(
            y_true_src, y_probs_src, thresholds=thresholds, class_names=class_names
        )
        source_results[str(src)] = metrics

    return source_results


def plot_and_save_confusion_matrices(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    thresholds: Dict[str, float],
    output_png: Path,
    model_name: str = "Model",
    class_names: List[str] = DEFAULT_CLASSES,
) -> None:
    """
    Renders and saves a 5-panel multi-label confusion matrix (TP, FP, FN, TN per class)
    as well as a pairwise co-occurrence confusion heatmap.
    """
    output_png.parent.mkdir(parents=True, exist_ok=True)

    y_pred = np.zeros_like(y_true, dtype=int)
    for i, cls in enumerate(class_names):
        t = thresholds.get(cls, 0.50)
        y_pred[:, i] = (y_probs[:, i] >= t).astype(int)

    mcm = multilabel_confusion_matrix(y_true, y_pred)

    fig, axes = plt.subplots(1, 5, figsize=(18, 3.5), sharey=True)
    for i, cls in enumerate(class_names):
        tn, fp, fn, tp = mcm[i].ravel()
        cm_matrix = np.array([[tn, fp], [fn, tp]])
        sns.heatmap(
            cm_matrix,
            annot=True,
            fmt="d",
            cmap="Blues",
            cbar=False,
            ax=axes[i],
            xticklabels=["Neg", "Pos"],
            yticklabels=["Neg", "Pos"],
        )
        t_val = thresholds.get(cls, 0.50)
        axes[i].set_title(f"{cls}\n(t={t_val:.2f})", fontsize=10)
        axes[i].set_xlabel("Predicted")
        if i == 0:
            axes[i].set_ylabel("Actual")

    plt.suptitle(f"{model_name} Multi-Label Confusion Matrices (Proxy Test)", fontsize=13, y=1.05)
    plt.tight_layout()
    plt.savefig(output_png, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"Confusion matrix figure saved: {output_png}")


def save_evaluation_report(
    metrics: Dict[str, any],
    output_json: Path,
) -> None:
    """Saves structured evaluation report JSON."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Evaluation metrics JSON saved: {output_json}")
