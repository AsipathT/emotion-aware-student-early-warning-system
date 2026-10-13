"""
backend/app/services/validation_stats.py

Feature 36: Pure Statistical Evaluation Helpers for Ground-Truth Validation.
Includes:
  - Cohen's Kappa (inter-rater agreement & model-vs-counsellor) with Landis-Koch bands
  - Confusion Matrix & Per-Class Precision/Recall/Macro-F1
  - Information Retrieval metrics for C4 recommendations: Precision@K and NDCG@K
"""

import math
from typing import Any, Dict, List, Optional, Set, Tuple


def get_kappa_band(kappa: float) -> str:
    """
    Returns standard Landis & Koch (1977) plain-language agreement interpretation band.
    """
    if kappa < 0.0:
        return "Poor (< 0.00)"
    if kappa <= 0.20:
        return "Slight (0.00 - 0.20)"
    if kappa <= 0.40:
        return "Fair (0.21 - 0.40)"
    if kappa <= 0.60:
        return "Moderate (0.41 - 0.60)"
    if kappa <= 0.80:
        return "Substantial (0.61 - 0.80)"
    return "Almost Perfect (0.81 - 1.00)"


def cohen_kappa(rater_a: List[str], rater_b: List[str]) -> Tuple[float, str]:
    """
    Computes Cohen's kappa coefficient (k) between two raters (or counsellor vs model).
    Returns (kappa, band).
    """
    if not rater_a or not rater_b or len(rater_a) != len(rater_b):
        return (0.0, "N/A (insufficient data)")

    n = len(rater_a)
    if n == 0:
        return (0.0, "N/A")

    # 1. Observed agreement (p_o)
    matches = sum(1 for a, b in zip(rater_a, rater_b) if str(a).strip() == str(b).strip())
    p_o = matches / n

    # 2. Expected chance agreement (p_e)
    all_classes = set(rater_a) | set(rater_b)
    p_e = 0.0
    for cls in all_classes:
        count_a = sum(1 for a in rater_a if a == cls)
        count_b = sum(1 for b in rater_b if b == cls)
        p_e += (count_a / n) * (count_b / n)

    # 3. Kappa calculation
    if math.isclose(1.0 - p_e, 0.0, abs_tol=1e-9):
        # Perfect consensus by chance or constant raters
        k = 1.0 if math.isclose(p_o, 1.0, abs_tol=1e-9) else 0.0
    else:
        k = (p_o - p_e) / (1.0 - p_e)

    k = max(-1.0, min(1.0, round(k, 4)))
    return (k, get_kappa_band(k))


def confusion_matrix(
    pairs: List[Tuple[str, str]],
    classes: List[str],
) -> Dict[str, Dict[str, int]]:
    """
    Builds a 2D contingency table of counts:
      matrix[counsellor_truth][model_prediction] = count
    """
    matrix: Dict[str, Dict[str, int]] = {
        truth: {pred: 0 for pred in classes}
        for truth in classes
    }

    for truth, pred in pairs:
        t_clean = str(truth).strip()
        p_clean = str(pred).strip()
        if t_clean in matrix and p_clean in matrix[t_clean]:
            matrix[t_clean][p_clean] += 1
        else:
            # Fallback if unknown class encountered
            matrix.setdefault(t_clean, {}).setdefault(p_clean, 0)
            matrix[t_clean][p_clean] += 1

    return matrix


def per_class_precision_recall(
    pairs: List[Tuple[str, str]],
    classes: List[str],
) -> Tuple[Dict[str, Dict[str, float]], float]:
    """
    Evaluates model performance against counsellor ground truth.
    pairs: List of (truth, pred) tuples.
    Returns:
      (per_class_dict, macro_f1)
      where per_class_dict[cls] = {"precision": float, "recall": float, "f1": float, "support": int}
    """
    stats: Dict[str, Dict[str, float]] = {}
    f1_scores: List[float] = []

    for cls in classes:
        tp = sum(1 for t, p in pairs if t == cls and p == cls)
        fp = sum(1 for t, p in pairs if t != cls and p == cls)
        fn = sum(1 for t, p in pairs if t == cls and p != cls)
        support = sum(1 for t, _ in pairs if t == cls)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        stats[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
        }
        if support > 0 or (tp + fp) > 0:
            f1_scores.append(f1)

    macro_f1 = round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0
    return (stats, macro_f1)


def precision_at_k(suitable_ranks: List[int], k: int) -> float:
    """
    Precision at K for candidate recommendations ranking.
    Computes fraction of recommendations within the top-K ranks marked as suitable by the counsellor.
    suitable_ranks: 1-based ranks deemed clinically suitable (e.g. [1, 3])
    """
    if k <= 0:
        return 0.0
    suitable_set = set(suitable_ranks)
    hits = sum(1 for r in range(1, k + 1) if r in suitable_set)
    return round(hits / k, 4)


def ndcg_at_k(suitable_ranks: List[int], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain at rank K (NDCG@K) with binary relevance.
    DCG@K = sum_{r=1}^K (rel(r) / log2(r + 1))
    IDCG@K = sum_{r=1}^{min(K, |suitable|)} (1 / log2(r + 1))
    """
    if k <= 0 or not suitable_ranks:
        return 0.0

    suitable_set = set(suitable_ranks)

    # 1. DCG@K
    dcg = 0.0
    for r in range(1, k + 1):
        rel = 1.0 if r in suitable_set else 0.0
        if rel > 0:
            dcg += rel / math.log2(r + 1)

    # 2. IDCG@K (Ideal DCG where all suitable candidates are placed at the very top)
    n_suitable = len(suitable_ranks)
    ideal_hits = min(k, n_suitable)
    if ideal_hits == 0:
        return 0.0

    idcg = 0.0
    for r in range(1, ideal_hits + 1):
        idcg += 1.0 / math.log2(r + 1)

    if math.isclose(idcg, 0.0, abs_tol=1e-9):
        return 0.0

    return round(dcg / idcg, 4)


def calculate_c1_inter_rater_kappa(
    labels: List[Dict[str, Any]],
) -> Optional[Tuple[float, str]]:
    """
    Computes inter-rater Cohen's kappa across items labelled by >= 2 human reviewers.
    Returns None if fewer than 2 overlapping ratings exist across items.
    """
    # Group labels by item key (pid, course_id, week_index)
    item_groups: Dict[Tuple[str, str, int], Dict[str, str]] = {}
    for lbl in labels:
        key = (
            str(lbl.get("pid")),
            str(lbl.get("course_id")),
            int(lbl.get("week_index", 0)),
        )
        rev_id = str(lbl.get("reviewer_id"))
        choice = str(lbl.get("counsellor_label"))
        item_groups.setdefault(key, {})[rev_id] = choice

    # Identify items with at least two distinct reviewers
    multi_rated_items = [
        choices for choices in item_groups.values() if len(choices) >= 2
    ]

    if not multi_rated_items:
        return None

    # Collect pairs of ratings across distinct reviewers
    rater_a_labels: List[str] = []
    rater_b_labels: List[str] = []

    for choices in multi_rated_items:
        reviewers = sorted(choices.keys())
        # Pick the first two distinct reviewers for canonical pairwise agreement
        r1, r2 = reviewers[0], reviewers[1]
        rater_a_labels.append(choices[r1])
        rater_b_labels.append(choices[r2])

    if len(rater_a_labels) < 2:
        return None

    return cohen_kappa(rater_a_labels, rater_b_labels)
