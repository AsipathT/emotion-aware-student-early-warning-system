"""
backend/tests/test_feature36_validation.py

Feature 36: Statistical validation tests for Component 1 and Component 4.
Validates:
  - Cohen's kappa calculation and Landis-Koch bands.
  - Confusion matrix and per-class precision/recall/macro-F1 metrics.
  - Precision@K and NDCG@K ranking evaluation metrics against hand calculations.
  - Inter-rater agreement computation across multi-reviewed items.
"""

import math
import pytest

from app.services.validation_stats import (
    calculate_c1_inter_rater_kappa,
    cohen_kappa,
    confusion_matrix,
    get_kappa_band,
    ndcg_at_k,
    per_class_precision_recall,
    precision_at_k,
)
from app.models.validation import ValidationLabel, RecommendationRating


def test_cohen_kappa_perfect_agreement():
    """Validates that identical ratings produce kappa=1.0 and Almost Perfect band."""
    rater_a = ["exam_anxiety", "course_frustration", "none", "motivation_erosion"]
    rater_b = ["exam_anxiety", "course_frustration", "none", "motivation_erosion"]
    k, band = cohen_kappa(rater_a, rater_b)
    assert k == 1.0
    assert "Almost Perfect" in band


def test_cohen_kappa_hand_calculation():
    """
    Validates Cohen's kappa against a known contingency table:
    N = 10, Agree = 8, Chance agreement = 0.50
    p_o = 0.8, p_e = 0.5 -> kappa = (0.8 - 0.5) / (1 - 0.5) = 0.60
    """
    rater_a = ["yes"] * 5 + ["no"] * 5
    rater_b = ["yes"] * 4 + ["no"] * 1 + ["yes"] * 1 + ["no"] * 4
    # rater_a has 5 yes, 5 no (P = 0.5, 0.5)
    # rater_b has 5 yes, 5 no (P = 0.5, 0.5)
    # agreement: 4 + 4 = 8 matches -> p_o = 0.8
    # p_e = 0.5*0.5 + 0.5*0.5 = 0.5
    # kappa = (0.8 - 0.5) / 0.5 = 0.60
    k, band = cohen_kappa(rater_a, rater_b)
    assert math.isclose(k, 0.60, abs_tol=1e-3)
    assert "Moderate" in band


def test_precision_at_k():
    """
    Hand calculation test for Precision@K:
    Candidates = 3, Suitable ranks = [1, 3]
    rel = [1, 0, 1]
    P@1 = 1/1 = 1.0
    P@2 = 1/2 = 0.5
    P@3 = 2/3 ≈ 0.6667
    """
    suitable = [1, 3]
    assert precision_at_k(suitable, 1) == 1.0
    assert precision_at_k(suitable, 2) == 0.5
    assert math.isclose(precision_at_k(suitable, 3), 0.6667, abs_tol=1e-3)


def test_ndcg_at_k():
    """
    Hand calculation test for NDCG@K:
    Candidates = 3, Suitable ranks = [1, 3]
    rel = [1, 0, 1]
    DCG@3 = 1/log2(2) + 0/log2(3) + 1/log2(4) = 1.0 + 0.0 + 0.5 = 1.5
    Ideal rel = [1, 1, 0]
    IDCG@3 = 1/log2(2) + 1/log2(3) = 1.0 + 1/1.58496 = 1.0 + 0.63093 = 1.63093
    NDCG@3 = 1.5 / 1.63093 ≈ 0.9197
    """
    suitable = [1, 3]
    score = ndcg_at_k(suitable, 3)
    assert math.isclose(score, 0.9197, abs_tol=1e-3)


def test_confusion_matrix_and_metrics():
    """Validates 2D contingency table and per-class precision/recall."""
    classes = ["exam_anxiety", "none"]
    pairs = [
        ("exam_anxiety", "exam_anxiety"),
        ("exam_anxiety", "none"),
        ("none", "none"),
        ("none", "none"),
    ]
    matrix = confusion_matrix(pairs, classes)
    assert matrix["exam_anxiety"]["exam_anxiety"] == 1
    assert matrix["exam_anxiety"]["none"] == 1
    assert matrix["none"]["none"] == 2
    assert matrix["none"]["exam_anxiety"] == 0

    stats, macro_f1 = per_class_precision_recall(pairs, classes)
    # For exam_anxiety: TP=1, FP=0, FN=1 -> Prec=1.0, Rec=0.5, F1=2/3 ≈ 0.6667
    assert stats["exam_anxiety"]["precision"] == 1.0
    assert stats["exam_anxiety"]["recall"] == 0.5
    assert math.isclose(stats["exam_anxiety"]["f1"], 0.6667, abs_tol=1e-3)


def test_inter_rater_kappa():
    """Validates multi-reviewer pairwise kappa computation."""
    labels = [
        {"pid": "STU_1", "course_id": "CS1", "week_index": 1, "reviewer_id": "u1", "counsellor_label": "exam_anxiety"},
        {"pid": "STU_1", "course_id": "CS1", "week_index": 1, "reviewer_id": "u2", "counsellor_label": "exam_anxiety"},
        {"pid": "STU_2", "course_id": "CS1", "week_index": 2, "reviewer_id": "u1", "counsellor_label": "none"},
        {"pid": "STU_2", "course_id": "CS1", "week_index": 2, "reviewer_id": "u2", "counsellor_label": "none"},
    ]
    res = calculate_c1_inter_rater_kappa(labels)
    assert res is not None
    k, band = res
    assert k == 1.0
