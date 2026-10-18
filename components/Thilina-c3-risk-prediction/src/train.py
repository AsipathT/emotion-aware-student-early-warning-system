"""
components/Thilina-c3-risk-prediction/src/train.py

Training and Evaluation pipeline for Component 3 Multimodal Risk Model.
Implements:
  - Cohort-based split: Train on Cohort 1 & 2, Test on Cohort 3
  - Target: withdraws_within_k_weeks
  - Threshold tuning on validation fold
  - Baselines: Majority-Class Baseline & Logistic Regression Baseline
  - Metrics: ROC-AUC, PR-AUC, F1, Brier Calibration Score
  - Modality Attribution Accuracy against data/truth_labels.csv
"""

import os
import sys

# Ensure component root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    f1_score,
    brier_score_loss,
)
from src.model import MultimodalRiskModel, ALL_FEATURE_COLS


def find_optimal_threshold(y_true, y_probs, step=0.02):
    """Finds decision threshold maximizing F1 score on validation set."""
    best_thresh = 0.50
    best_f1 = -1.0
    for thresh in np.arange(0.05, 0.90, step):
        preds = (y_probs >= thresh).astype(int)
        score = f1_score(y_true, preds, zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_thresh = float(thresh)
    return best_thresh, best_f1


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "multimodal_risk_training_data.csv")
    truth_path = os.path.join(base_dir, "data", "truth_labels.csv")
    model_dir = os.path.join(base_dir, "models")

    if not os.path.exists(data_path) or not os.path.exists(truth_path):
        print("[*] Generating dataset and truth labels first...")
        from src.generate_multimodal_dataset import generate_multimodal_data
        train_df, truth_df = generate_multimodal_data(num_students=600, num_weeks=30, k_weeks=4)
        train_df.to_csv(data_path, index=False)
        truth_df.to_csv(truth_path, index=False)
    else:
        train_df = pd.read_csv(data_path)
        truth_df = pd.read_csv(truth_path)

    target_col = "withdraws_within_k_weeks"

    # ── 1. Cohort-Based Split (Train on Cohort 1 & 2, Test on Cohort 3) ────────
    train_val_df = train_df[train_df["cohort"].isin(["cohort_1", "cohort_2"])].copy()
    test_df = train_df[train_df["cohort"] == "cohort_3"].copy()

    # Split train_val_df into train (Cohort 1) and validation (Cohort 2) for threshold tuning
    train_mask = train_val_df["cohort"] == "cohort_1"
    val_mask = train_val_df["cohort"] == "cohort_2"

    X_train = train_val_df[train_mask][ALL_FEATURE_COLS]
    y_train = train_val_df[train_mask][target_col].values

    X_val = train_val_df[val_mask][ALL_FEATURE_COLS]
    y_val = train_val_df[val_mask][target_col].values

    X_test = test_df[ALL_FEATURE_COLS]
    y_test = test_df[target_col].values

    print(f"[*] Train set (Cohort 1): {len(X_train)} rows ({y_train.sum()} positives, {y_train.mean()*100:.1f}%)")
    print(f"[*] Val set   (Cohort 2): {len(X_val)} rows ({y_val.sum()} positives, {y_val.mean()*100:.1f}%)")
    print(f"[*] Test set  (Cohort 3): {len(X_test)} rows ({y_test.sum()} positives, {y_test.mean()*100:.1f}%)")

    # ── 2. Baseline 1: Majority-Class Baseline ─────────────────────────────────
    p_train_prior = float(y_train.mean())
    maj_probs = np.full_like(y_test, fill_value=p_train_prior, dtype=float)
    maj_preds = np.zeros_like(y_test)

    maj_roc_auc = 0.5000
    maj_pr_auc = float(average_precision_score(y_test, maj_probs))
    maj_f1 = float(f1_score(y_test, maj_preds, zero_division=0))
    maj_calib = float(brier_score_loss(y_test, maj_probs))

    # ── 3. Baseline 2: Logistic Regression Baseline ────────────────────────────
    from src.model import MultimodalRiskModel
    temp_model = MultimodalRiskModel()
    X_train_trans = temp_model.preprocessor.fit_transform(X_train)
    X_val_trans = temp_model.preprocessor.transform(X_val)
    X_test_trans = temp_model.preprocessor.transform(X_test)

    lr_clf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    lr_clf.fit(X_train_trans, y_train)

    lr_val_probs = lr_clf.predict_proba(X_val_trans)[:, 1]
    lr_thresh, _ = find_optimal_threshold(y_val, lr_val_probs)

    lr_test_probs = lr_clf.predict_proba(X_test_trans)[:, 1]
    lr_test_preds = (lr_test_probs >= lr_thresh).astype(int)

    lr_roc_auc = float(roc_auc_score(y_test, lr_test_probs))
    lr_pr_auc = float(average_precision_score(y_test, lr_test_probs))
    lr_f1 = float(f1_score(y_test, lr_test_preds, zero_division=0))
    lr_calib = float(brier_score_loss(y_test, lr_test_probs))

    # ── 4. Main Model: C3 Multimodal Gradient Boosting ─────────────────────────
    # Train on full Cohort 1 & 2 for final model, using val threshold
    model = MultimodalRiskModel(n_estimators=140, max_depth=5, learning_rate=0.08, random_state=42)
    model.fit(train_val_df[ALL_FEATURE_COLS], train_val_df[target_col].values)

    # Use validation fold for threshold tuning
    val_trans = model.preprocessor.transform(X_val)
    c3_val_probs = model.clf.predict_proba(val_trans)[:, 1]
    c3_thresh, _ = find_optimal_threshold(y_val, c3_val_probs)

    c3_test_trans = model.preprocessor.transform(X_test)
    c3_test_probs = model.clf.predict_proba(c3_test_trans)[:, 1]
    c3_test_preds = (c3_test_probs >= c3_thresh).astype(int)

    c3_roc_auc = float(roc_auc_score(y_test, c3_test_probs))
    c3_pr_auc = float(average_precision_score(y_test, c3_test_probs))
    c3_f1 = float(f1_score(y_test, c3_test_preds, zero_division=0))
    c3_calib = float(brier_score_loss(y_test, c3_test_probs))

    # ── 5. Attribution Accuracy Evaluation ─────────────────────────────────────
    # Evaluate how often the top SHAP modality equals the planted driver
    print("[*] Computing SHAP explainability and attribution accuracy...")
    test_predictions = model.predict_risk(X_test)

    # Merge predictions with test_df and ground truth
    test_eval_df = test_df[["pid", "week_index", target_col]].copy()
    test_eval_df["predicted_score"] = c3_test_probs
    test_eval_df["predicted_label"] = c3_test_preds
    test_eval_df["top_modality"] = [p["top_modality"] for p in test_predictions]

    merged_truth = test_eval_df.merge(
        truth_df[["pid", "planted_driver", "onset_week", "withdraw_week"]],
        on="pid",
        how="left",
    )

    # Focus on true positive at-risk instances where student is in crisis with planted driver
    crisis_instances = merged_truth[
        (merged_truth[target_col] == 1) & (merged_truth["planted_driver"].isin(["affective", "behavioural", "academic"]))
    ]

    if len(crisis_instances) > 0:
        correct_attributions = (crisis_instances["top_modality"] == crisis_instances["planted_driver"]).sum()
        attribution_acc = float((correct_attributions / len(crisis_instances)) * 100)
    else:
        attribution_acc = 0.0

    # Save model artifacts
    model.save(model_dir)
    print(f"[OK] Model artifacts saved to {model_dir}")

    # Output results
    results = {
        "Majority-Class Baseline": {
            "ROC-AUC": f"{maj_roc_auc:.4f}",
            "PR-AUC": f"{maj_pr_auc:.4f}",
            "F1-Score": f"{maj_f1:.4f}",
            "Brier Calibration": f"{maj_calib:.4f}",
            "Attribution Accuracy": "N/A",
        },
        "Logistic Regression Baseline": {
            "ROC-AUC": f"{lr_roc_auc:.4f}",
            "PR-AUC": f"{lr_pr_auc:.4f}",
            "F1-Score": f"{lr_f1:.4f} (thresh={lr_thresh:.2f})",
            "Brier Calibration": f"{lr_calib:.4f}",
            "Attribution Accuracy": "N/A",
        },
        "C3 Multimodal Model (Synthetic)": {
            "ROC-AUC": f"{c3_roc_auc:.4f}",
            "PR-AUC": f"{c3_pr_auc:.4f}",
            "F1-Score": f"{c3_f1:.4f} (thresh={c3_thresh:.2f})",
            "Brier Calibration": f"{c3_calib:.4f}",
            "Attribution Accuracy": f"{attribution_acc:.1f}%",
        },
    }

    results_df = pd.DataFrame(results).T
    print("\n" + "=" * 80)
    print("  MODEL BENCHMARKING REPORT (EVALUATED ON UNSEEN COHORT 3 - SYNTHETIC)")
    print("=" * 80)
    print(results_df.to_string())
    print("=" * 80)
    return results_df


if __name__ == "__main__":
    main()
