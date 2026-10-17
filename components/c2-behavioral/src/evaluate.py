"""
Evaluation metrics for Component 2 trajectory classification.
Computes macro-F1, overall accuracy, per-class metrics, and confusion matrix.
"""

from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

DEFAULT_LABELS: List[str] = ["declining", "improving", "stable", "volatile"]


def evaluate(
    y_true: Any,
    y_pred: Any,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates classification performance against specified labels:
      - macro_f1: Macro-averaged F1 score
      - accuracy: Overall accuracy
      - per_class: precision, recall, f1, support per label
      - confusion_matrix: list of lists (rows=true, cols=pred)
    """
    if labels is None:
        labels = DEFAULT_LABELS

    y_t = np.asarray(y_true)
    y_p = np.asarray(y_pred)

    macro_f1 = float(f1_score(y_t, y_p, average="macro", zero_division=0))
    acc = float(accuracy_score(y_t, y_p))

    precision, recall, f1, support = precision_recall_fscore_support(
        y_t, y_p, labels=labels, zero_division=0
    )

    per_class: Dict[str, Dict[str, Any]] = {}
    for i, lbl in enumerate(labels):
        per_class[lbl] = {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }

    cm = confusion_matrix(y_t, y_p, labels=labels).tolist()

    return {
        "macro_f1": macro_f1,
        "accuracy": acc,
        "per_class": per_class,
        "confusion_matrix": cm,
    }
