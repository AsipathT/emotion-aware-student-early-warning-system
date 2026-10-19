"""
src/baselines.py

Baseline models for Component 1: Affective State Detection.
Implements:
1. TF-IDF + One-vs-Rest Logistic Regression (multi-label 5 distress classes).
2. VADER Sentiment Lexicon (coarse binary 'any distress' baseline).
3. Ablation mode: train on goemotions_proxy only.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.evaluation import (
    DEFAULT_CLASSES,
    compute_multilabel_metrics,
    compute_split_by_source_metrics,
    plot_and_save_confusion_matrices,
    save_evaluation_report,
    tune_thresholds_on_val,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("c1_baselines")


def run_tfidf_baseline(
    component_root: Path,
    ablation_source: Optional[str] = None,
    max_samples: Optional[int] = None,
    save_model: bool = True,
) -> Dict[str, any]:
    """
    Trains One-vs-Rest Logistic Regression with TF-IDF features on train.csv.
    Tunes thresholds on val.csv, and evaluates test_proxy.csv once.
    """
    processed_dir = component_root / "data" / "processed"
    reports_metrics_dir = component_root / "reports" / "metrics"
    reports_figures_dir = component_root / "reports" / "figures"
    models_dir = component_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(processed_dir / "train.csv")
    val_df = pd.read_csv(processed_dir / "val.csv")
    test_df = pd.read_csv(processed_dir / "test_proxy.csv")

    if ablation_source:
        logger.info(f"Applying ablation: Filtering training data to source='{ablation_source}'")
        train_df = train_df[train_df["source"] == ablation_source].copy()

    if max_samples and max_samples > 0:
        logger.info(f"Smoke-test sampling: train={max_samples}")
        train_df = train_df.iloc[:max_samples].copy()
        val_df = val_df.iloc[: max(50, int(max_samples * 0.15))].copy()
        test_df = test_df.iloc[: max(50, int(max_samples * 0.15))].copy()

    logger.info(f"TF-IDF training size: {len(train_df)} samples")

    # Vectorizer
    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
    )
    X_train = vectorizer.fit_transform(train_df["text"].fillna(""))
    X_val = vectorizer.transform(val_df["text"].fillna(""))
    X_test = vectorizer.transform(test_df["text"].fillna(""))

    # Train 5 independent Logistic Regression models (One-vs-Rest multi-label)
    models: Dict[str, LogisticRegression] = {}
    val_probs = np.zeros((len(val_df), len(DEFAULT_CLASSES)), dtype=float)
    test_probs = np.zeros((len(test_df), len(DEFAULT_CLASSES)), dtype=float)

    for i, cls in enumerate(DEFAULT_CLASSES):
        y_train_c = train_df[cls].values.astype(int)
        # Handle cases with no positive examples in sample
        if y_train_c.sum() == 0:
            val_probs[:, i] = 0.0
            test_probs[:, i] = 0.0
            continue

        clf = LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        )
        clf.fit(X_train, y_train_c)
        models[cls] = clf

        val_probs[:, i] = clf.predict_proba(X_val)[:, 1]
        test_probs[:, i] = clf.predict_proba(X_test)[:, 1]

    # Tune per-class thresholds on val.csv only
    y_val_true = val_df[DEFAULT_CLASSES].values.astype(int)
    thresholds = tune_thresholds_on_val(y_val_true, val_probs, class_names=DEFAULT_CLASSES)

    # Save tuned thresholds
    thresh_filename = "thresholds_tfidf_ablation.json" if ablation_source else "thresholds_tfidf.json"
    with open(models_dir / thresh_filename, "w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)

    # Evaluate test_proxy.csv ONCE
    y_test_true = test_df[DEFAULT_CLASSES].values.astype(int)
    test_overall = compute_multilabel_metrics(
        y_test_true, test_probs, thresholds=thresholds, class_names=DEFAULT_CLASSES
    )

    # Segment by source
    test_by_source = compute_split_by_source_metrics(
        test_df, test_probs, thresholds=thresholds, class_names=DEFAULT_CLASSES
    )

    # Plot confusion matrix
    fig_name = "confusion_matrix_tfidf_ablation.png" if ablation_source else "confusion_matrix_tfidf.png"
    plot_and_save_confusion_matrices(
        y_test_true,
        test_probs,
        thresholds=thresholds,
        output_png=reports_figures_dir / fig_name,
        model_name="TF-IDF + LogisticRegression" + (f" (Ablation: {ablation_source})" if ablation_source else ""),
        class_names=DEFAULT_CLASSES,
    )

    result = {
        "model_name": "TF-IDF + Logistic Regression",
        "evaluation_type": "proxy test",
        "ablation_training_source": ablation_source or "all_sources",
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_proxy_samples": len(test_df),
        "tuned_val_thresholds": thresholds,
        "overall_test_proxy_metrics": test_overall,
        "metrics_by_source": test_by_source,
    }

    out_json = (
        reports_metrics_dir / "ablation_tfidf_goemotions.json"
        if ablation_source
        else reports_metrics_dir / "baseline_tfidf.json"
    )
    save_evaluation_report(result, out_json)

    if save_model and not ablation_source:
        joblib.dump(vectorizer, models_dir / "tfidf_vectorizer.joblib")
        joblib.dump(models, models_dir / "tfidf_logreg_models.joblib")

    return result


def run_vader_baseline(component_root: Path) -> Dict[str, any]:
    """
    Evaluates VADER sentiment lexicon on test_proxy.csv as a binary 'any distress' baseline.
    VADER cannot distinguish between the 5 educational distress classes.
    """
    processed_dir = component_root / "data" / "processed"
    reports_metrics_dir = component_root / "reports" / "metrics"

    test_df = pd.read_csv(processed_dir / "test_proxy.csv")
    analyzer = SentimentIntensityAnalyzer()

    # Ground truth: any distress if any of the 5 distress classes == 1
    y_true_binary = (test_df[DEFAULT_CLASSES].sum(axis=1) > 0).astype(int).values

    compound_scores = []
    for text in test_df["text"].fillna(""):
        scores = analyzer.polarity_scores(text)
        compound_scores.append(scores["compound"])

    compound_scores = np.array(compound_scores)
    # Standard VADER threshold for negative sentiment: compound <= -0.05
    y_pred_binary = (compound_scores <= -0.05).astype(int)
    # Approximate probability of distress: sigmoid of -compound
    probs_distress = 1.0 / (1.0 + np.exp(compound_scores * 3.0))

    prec = float(precision_score(y_true_binary, y_pred_binary, zero_division=0))
    rec = float(recall_score(y_true_binary, y_pred_binary, zero_division=0))
    f1 = float(f1_score(y_true_binary, y_pred_binary, zero_division=0))
    acc = float(accuracy_score(y_true_binary, y_pred_binary))
    auc = float(roc_auc_score(y_true_binary, probs_distress))

    # Segment by source
    by_source: Dict[str, any] = {}
    for src in test_df["source"].unique():
        idx = (test_df["source"] == src).values
        yt = y_true_binary[idx]
        yp = y_pred_binary[idx]
        probs = probs_distress[idx]
        by_source[str(src)] = {
            "samples": int(len(yt)),
            "precision": round(float(precision_score(yt, yp, zero_division=0)), 4),
            "recall": round(float(recall_score(yt, yp, zero_division=0)), 4),
            "f1": round(float(f1_score(yt, yp, zero_division=0)), 4),
            "accuracy": round(float(accuracy_score(yt, yp)), 4),
            "roc_auc": round(float(roc_auc_score(yt, probs)), 4) if len(np.unique(yt)) > 1 else 0.50,
        }

    report = {
        "model_name": "VADER Sentiment Lexicon (Binary Baseline)",
        "evaluation_type": "proxy test",
        "description": (
            "VADER is evaluated strictly as a coarse binary 'any distress' detector. "
            "Because VADER is a generic rule-based sentiment lexicon lacking pedagogical/academic "
            "semantic understanding, it CANNOT separate or classify the 5 fine-grained academic distress classes."
        ),
        "decision_rule": "predicted_distress = (compound <= -0.05)",
        "test_proxy_total_samples": len(test_df),
        "overall_binary_metrics": {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(auc, 4),
            "true_distress_count": int(y_true_binary.sum()),
            "predicted_distress_count": int(y_pred_binary.sum()),
        },
        "binary_metrics_by_source": by_source,
    }

    save_evaluation_report(report, reports_metrics_dir / "baseline_vader.json")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run baseline models for C1 Affective State Detection")
    parser.add_argument(
        "--baseline",
        choices=["tfidf", "vader", "all", "ablation"],
        default="all",
        help="Which baseline to execute",
    )
    parser.add_argument("--max-samples", type=int, default=None, help="Max samples for smoke test")
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[1]

    if args.baseline in ["vader", "all"]:
        logger.info("Executing VADER binary baseline...")
        v_res = run_vader_baseline(component_root)
        print("\n" + "=" * 60)
        print("VADER BASELINE (Binary 'Any Distress' - Proxy Test)")
        print("=" * 60)
        for k, v in v_res["overall_binary_metrics"].items():
            print(f"  {k:25s}: {v}")
        print("=" * 60 + "\n")

    if args.baseline in ["tfidf", "all"]:
        logger.info("Executing TF-IDF + Logistic Regression baseline...")
        t_res = run_tfidf_baseline(component_root, max_samples=args.max_samples)
        print("\n" + "=" * 60)
        print("TF-IDF + LOGISTIC REGRESSION (Multi-label - Proxy Test)")
        print("=" * 60)
        print(f"Macro F1:        {t_res['overall_test_proxy_metrics']['macro_metrics']['macro_f1']:.4f}")
        print(f"Macro Precision: {t_res['overall_test_proxy_metrics']['macro_metrics']['macro_precision']:.4f}")
        print(f"Macro Recall:    {t_res['overall_test_proxy_metrics']['macro_metrics']['macro_recall']:.4f}")
        print(f"Macro ROC-AUC:   {t_res['overall_test_proxy_metrics']['macro_metrics']['macro_roc_auc']:.4f}")
        print("\nPer-Class Metrics:")
        for cls, m in t_res["overall_test_proxy_metrics"]["per_class_metrics"].items():
            print(f"  {cls:24s} | P: {m['precision']:.4f} | R: {m['recall']:.4f} | F1: {m['f1']:.4f} | AUC: {m['roc_auc']:.4f}")
        print("=" * 60 + "\n")

    if args.baseline in ["ablation", "all"]:
        logger.info("Executing TF-IDF Ablation (GoEmotions only)...")
        a_res = run_tfidf_baseline(
            component_root,
            ablation_source="goemotions_proxy",
            max_samples=args.max_samples,
            save_model=False,
        )
        print("\n" + "=" * 60)
        print("TF-IDF ABLATION (GoEmotions-Only Training - Proxy Test)")
        print("=" * 60)
        print(f"Macro F1:        {a_res['overall_test_proxy_metrics']['macro_metrics']['macro_f1']:.4f}")
        for cls, m in a_res["overall_test_proxy_metrics"]["per_class_metrics"].items():
            print(f"  {cls:24s} | P: {m['precision']:.4f} | R: {m['recall']:.4f} | F1: {m['f1']:.4f} | AUC: {m['roc_auc']:.4f}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
