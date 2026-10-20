"""
components/Thilina-c3-risk-prediction/src/train.py

Training and Evaluation pipeline for Component 3 Multimodal Risk Model.
Implements:
  - Cohort-based split: Train on Cohort 1, Tune threshold on Cohort 2, Test on Cohort 3
  - Target: withdraws_within_k_weeks
  - Threshold tuning on validation fold
  - Baselines: Majority-Class Baseline & Logistic Regression Baseline
  - Metrics: ROC-AUC, PR-AUC, F1, Brier score, ECE, Positive Rate, Confusion Counts (TN, FP, FN, TP)
  - Modality Attribution:
      * Modality-level permutation attribution (20 repeats per modality)
      * Primary evaluation: first 3 weeks post-onset with observed affect (message_count > 0)
      * Secondary evaluation: all crisis student rows
      * 3x3 confusion matrix and per-driver accuracy
      * 95% bootstrap confidence interval
      * Normalized SHAP secondary report
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
    confusion_matrix,
)
import shap

from src.model import MultimodalRiskModel, ALL_FEATURE_COLS, BiLSTMRiskModel

AFFECTIVE_COLS = [
    "message_count",
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "confidence",
    "stress_label",
]

BEHAVIORAL_COLS = [
    "login_count",
    "session_minutes",
    "clicks",
    "video_play_count",
    "video_pause_count",
    "video_rewind_count",
    "video_skip_count",
    "video_completion_pct",
    "submissions_count",
    "avg_submission_delay_hours",
    "trajectory_label",
]

ACADEMIC_COLS = [
    "attendance_pct",
    "ca_marks",
    "midterm_mark",
    "quiz_score",
    "submission_delay_hours",
]

MODALITIES = {
    "affective": AFFECTIVE_COLS,
    "behavioural": BEHAVIORAL_COLS,
    "academic": ACADEMIC_COLS,
}


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error across equal-width probability bins."""
    bin_limits = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        low, high = bin_limits[i], bin_limits[i + 1]
        mask = (y_prob >= low) & (y_prob < high if i < n_bins - 1 else y_prob <= high)
        bin_count = np.sum(mask)
        if bin_count > 0:
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            ece += (bin_count / n) * np.abs(bin_acc - bin_conf)
    return float(ece)


def find_optimal_threshold(y_true: np.ndarray, y_probs: np.ndarray, step: float = 0.02) -> tuple:
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


def compute_modality_permutation_attribution(
    sub_df: pd.DataFrame, model: MultimodalRiskModel, n_repeats: int = 20, seed: int = 123
) -> tuple:
    """
    Shuffles each modality's columns across rows (repeated n_repeats times)
    and measures the drop in predicted risk. The modality with the largest mean
    drop is the attributed driver.
    """
    X_sub = sub_df[ALL_FEATURE_COLS].copy()
    X_sub_trans = model.preprocessor.transform(X_sub)
    base_probs = model.clf.predict_proba(X_sub_trans)[:, 1]

    rng = np.random.RandomState(seed)
    drops = {m: np.zeros(len(sub_df)) for m in MODALITIES}

    for m_name, m_cols in MODALITIES.items():
        for _ in range(n_repeats):
            X_perm = X_sub.copy()
            perm_idx = rng.permutation(len(X_sub))
            X_perm[m_cols] = X_sub[m_cols].iloc[perm_idx].values
            X_perm_trans = model.preprocessor.transform(X_perm)
            perm_probs = model.clf.predict_proba(X_perm_trans)[:, 1]
            drops[m_name] += (base_probs - perm_probs) / float(n_repeats)

    attributed = []
    for idx in range(len(sub_df)):
        d_i = {m: drops[m][idx] for m in MODALITIES}
        best = max(d_i, key=d_i.get)
        attributed.append(best)
    return attributed, drops


def compute_normalized_shap_attribution(sub_df: pd.DataFrame, model: MultimodalRiskModel) -> list:
    """Computes secondary SHAP attribution normalized by the number of features in each modality."""
    explainer = shap.TreeExplainer(model.clf)
    X_trans = model.preprocessor.transform(sub_df[ALL_FEATURE_COLS])
    shap_vals = explainer.shap_values(X_trans)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]

    feat_names = list(model.preprocessor.get_feature_names_out())
    mod_feat_indices = {m: [] for m in MODALITIES}
    for f_idx, f_name in enumerate(feat_names):
        clean = f_name.replace("num__", "").replace("cat__", "")
        if any(clean.startswith(col) for col in AFFECTIVE_COLS):
            mod_feat_indices["affective"].append(f_idx)
        elif any(clean.startswith(col) for col in BEHAVIORAL_COLS):
            mod_feat_indices["behavioural"].append(f_idx)
        else:
            mod_feat_indices["academic"].append(f_idx)

    shap_attributed = []
    for i in range(len(sub_df)):
        mean_abs_shaps = {}
        for m in MODALITIES:
            idx_list = mod_feat_indices[m]
            if idx_list:
                mean_abs_shaps[m] = float(np.mean(np.abs(shap_vals[i, idx_list])))
            else:
                mean_abs_shaps[m] = 0.0
        shap_attributed.append(max(mean_abs_shaps, key=mean_abs_shaps.get))
    return shap_attributed


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "multimodal_risk_training_data.csv")
    truth_path = os.path.join(base_dir, "data", "truth_labels.csv")
    model_dir = os.path.join(base_dir, "models")

    if not os.path.exists(data_path) or not os.path.exists(truth_path):
        print("[*] Generating dataset and truth labels first...")
        from src.generate_multimodal_dataset import generate_multimodal_data
        train_df, truth_df = generate_multimodal_data(num_students=600, num_weeks=30, k_weeks=4, seed=42)
        train_df.to_csv(data_path, index=False)
        truth_df.to_csv(truth_path, index=False)
    else:
        train_df = pd.read_csv(data_path)
        truth_df = pd.read_csv(truth_path)

    target_col = "withdraws_within_k_weeks"

    # ── 1. Cohort-Based Split ──────────────────────────────────────────────────
    train_mask = train_df["cohort"] == "cohort_1"
    val_mask = train_df["cohort"] == "cohort_2"
    test_mask = train_df["cohort"] == "cohort_3"

    X_train = train_df[train_mask][ALL_FEATURE_COLS]
    y_train = train_df[train_mask][target_col].values

    X_val = train_df[val_mask][ALL_FEATURE_COLS]
    y_val = train_df[val_mask][target_col].values

    X_test = train_df[test_mask][ALL_FEATURE_COLS]
    y_test = train_df[test_mask][target_col].values

    test_pos_rate = float(np.mean(y_test))
    print(f"[*] Train set (Cohort 1): {len(X_train)} rows ({y_train.sum()} positives, {y_train.mean()*100:.1f}%)")
    print(f"[*] Val set   (Cohort 2): {len(X_val)} rows ({y_val.sum()} positives, {y_val.mean()*100:.1f}%)")
    print(f"[*] Test set  (Cohort 3): {len(X_test)} rows ({y_test.sum()} positives, {test_pos_rate*100:.2f}%)")

    # ── 2. Baseline 1: Majority-Class Baseline ─────────────────────────────────
    p_train_prior = float(y_train.mean())
    maj_test_probs = np.full_like(y_test, fill_value=p_train_prior, dtype=float)
    maj_test_preds = np.zeros_like(y_test)

    maj_roc = 0.5000
    maj_pr = test_pos_rate
    maj_f1 = float(f1_score(y_test, maj_test_preds, zero_division=0))
    maj_brier = float(brier_score_loss(y_test, maj_test_probs))
    maj_ece = compute_ece(y_test, maj_test_probs)
    maj_pos_rate = float(np.mean(maj_test_preds))
    maj_tn, maj_fp, maj_fn, maj_tp = confusion_matrix(y_test, maj_test_preds).ravel()

    # ── 3. Baseline 2: Logistic Regression Baseline ────────────────────────────
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

    lr_roc = float(roc_auc_score(y_test, lr_test_probs))
    lr_pr = float(average_precision_score(y_test, lr_test_probs))
    lr_f1 = float(f1_score(y_test, lr_test_preds, zero_division=0))
    lr_brier = float(brier_score_loss(y_test, lr_test_probs))
    lr_ece = compute_ece(y_test, lr_test_probs)
    lr_pos_rate = float(np.mean(lr_test_preds))
    lr_tn, lr_fp, lr_fn, lr_tp = confusion_matrix(y_test, lr_test_preds).ravel()

    # ── 4. Deep Learning Sequence Model: BiLSTM ────────────────────────────────
    print("[*] Training PyTorch BiLSTM Sequence Model (W=5 temporal windows)...")
    bilstm = BiLSTMRiskModel(
        hidden_dim=48,
        num_layers=2,
        dropout=0.25,
        window_size=5,
        lr=0.0015,
        epochs=12,
        batch_size=128,
        random_state=42,
    )
    bilstm.fit(train_df[train_mask], y_train, preprocessor=temp_model.preprocessor)

    bilstm_val_probs = bilstm.predict_proba(train_df[val_mask])
    bilstm_thresh, _ = find_optimal_threshold(y_val, bilstm_val_probs)

    bilstm_test_probs = bilstm.predict_proba(train_df[test_mask])
    bilstm_test_preds = (bilstm_test_probs >= bilstm_thresh).astype(int)

    bilstm_roc = float(roc_auc_score(y_test, bilstm_test_probs))
    bilstm_pr = float(average_precision_score(y_test, bilstm_test_probs))
    bilstm_f1 = float(f1_score(y_test, bilstm_test_preds, zero_division=0))
    bilstm_brier = float(brier_score_loss(y_test, bilstm_test_probs))
    bilstm_ece = compute_ece(y_test, bilstm_test_probs)
    bilstm_pos_rate = float(np.mean(bilstm_test_preds))
    bilstm_tn, bilstm_fp, bilstm_fn, bilstm_tp = confusion_matrix(y_test, bilstm_test_preds).ravel()

    bilstm.save(model_dir)
    print(f"[OK] BiLSTM model checkpoint saved to {model_dir}")

    # ── 5. Main Model: C3 Multimodal Gradient Boosting ─────────────────────────
    model = MultimodalRiskModel(n_estimators=150, max_depth=5, learning_rate=0.08, random_state=42)
    model.fit(X_train, y_train)

    c3_val_probs = model.clf.predict_proba(model.preprocessor.transform(X_val))[:, 1]
    c3_thresh, _ = find_optimal_threshold(y_val, c3_val_probs)

    c3_test_trans = model.preprocessor.transform(X_test)
    c3_test_probs = model.clf.predict_proba(c3_test_trans)[:, 1]
    c3_test_preds = (c3_test_probs >= c3_thresh).astype(int)

    c3_roc = float(roc_auc_score(y_test, c3_test_probs))
    c3_pr = float(average_precision_score(y_test, c3_test_probs))
    c3_f1 = float(f1_score(y_test, c3_test_preds, zero_division=0))
    c3_brier = float(brier_score_loss(y_test, c3_test_probs))
    c3_ece = compute_ece(y_test, c3_test_probs)
    c3_pos_rate = float(np.mean(c3_test_preds))
    c3_tn, c3_fp, c3_fn, c3_tp = confusion_matrix(y_test, c3_test_preds).ravel()

    # Save model artifacts
    model.save(model_dir)
    print(f"[OK] Model artifacts saved to {model_dir}")

    # Print Table 1: Metrics Table
    metrics_table = pd.DataFrame({
        "ROC-AUC": [f"{maj_roc:.4f}", f"{lr_roc:.4f}", f"{bilstm_roc:.4f}", f"{c3_roc:.4f}"],
        "PR-AUC": [f"{maj_pr:.4f}", f"{lr_pr:.4f}", f"{bilstm_pr:.4f}", f"{c3_pr:.4f}"],
        "F1 (Val Threshold)": [
            f"{maj_f1:.4f} (th=0.50)",
            f"{lr_f1:.4f} (th={lr_thresh:.2f})",
            f"{bilstm_f1:.4f} (th={bilstm_thresh:.2f})",
            f"{c3_f1:.4f} (th={c3_thresh:.2f})",
        ],
        "Brier Score": [f"{maj_brier:.4f}", f"{lr_brier:.4f}", f"{bilstm_brier:.4f}", f"{c3_brier:.4f}"],
        "ECE": [f"{maj_ece:.4f}", f"{lr_ece:.4f}", f"{bilstm_ece:.4f}", f"{c3_ece:.4f}"],
        "Positive Rate": [f"{maj_pos_rate:.4f}", f"{lr_pos_rate:.4f}", f"{bilstm_pos_rate:.4f}", f"{c3_pos_rate:.4f}"],
        "Confusion Counts (TN, FP, FN, TP)": [
            f"({maj_tn}, {maj_fp}, {maj_fn}, {maj_tp})",
            f"({lr_tn}, {lr_fp}, {lr_fn}, {lr_tp})",
            f"({bilstm_tn}, {bilstm_fp}, {bilstm_fn}, {bilstm_tp})",
            f"({c3_tn}, {c3_fp}, {c3_fn}, {c3_tp})",
        ],
    }, index=[
        "Majority-Class Baseline",
        "Logistic Regression",
        "BiLSTM Sequence Model",
        "C3 Gradient-Boosting Model",
    ])

    print("\n" + "=" * 80)
    print(f"  TEST-SET (COHORT_3) METRICS TABLE (Test Positive Rate: {test_pos_rate:.4f})")
    print("=" * 80)
    print(metrics_table.to_string())
    print("=" * 80)

    # ── 5. Attribution Evaluation ──────────────────────────────────────────────
    print("\n[*] Evaluating Modality-Level Permutation Attribution...")
    test_full = train_df[test_mask].copy()
    test_full = test_full.merge(
        truth_df[["pid", "planted_driver", "onset_week", "withdraw_week"]],
        on="pid",
        how="left",
    )

    # Primary condition: first 3 weeks post-onset with observed affect (message_count > 0)
    cond_3w = (
        (test_full["planted_driver"].isin(["affective", "behavioural", "academic"])) &
        (test_full["onset_week"].notna()) &
        (test_full["week_index"] >= test_full["onset_week"]) &
        (test_full["week_index"] <= test_full["onset_week"] + 3) &
        (test_full["message_count"] > 0)
    )
    eval_3w_df = test_full[cond_3w].copy()

    # All-rows condition: all crisis rows
    cond_all = test_full["planted_driver"].isin(["affective", "behavioural", "academic"])
    eval_all_df = test_full[cond_all].copy()

    eval_3w_df["attributed_driver"], _ = compute_modality_permutation_attribution(eval_3w_df, model, n_repeats=20, seed=123)
    correct_3w = (eval_3w_df["attributed_driver"] == eval_3w_df["planted_driver"]).sum()
    acc_3w = float(correct_3w / len(eval_3w_df)) * 100

    eval_all_df["attributed_driver"], _ = compute_modality_permutation_attribution(eval_all_df, model, n_repeats=20, seed=123)
    correct_all = (eval_all_df["attributed_driver"] == eval_all_df["planted_driver"]).sum()
    acc_all = float(correct_all / len(eval_all_df)) * 100

    # 95% Bootstrap Confidence Interval
    rng = np.random.RandomState(42)
    boot_accs = []
    for _ in range(1000):
        b_idx = rng.choice(len(eval_3w_df), size=len(eval_3w_df), replace=True)
        b_acc = (eval_3w_df["attributed_driver"].iloc[b_idx] == eval_3w_df["planted_driver"].iloc[b_idx]).mean() * 100
        boot_accs.append(b_acc)
    ci_low, ci_high = np.percentile(boot_accs, [2.5, 97.5])

    # Per-driver accuracy & Confusion Matrix
    drivers = ["affective", "behavioural", "academic"]
    cm_3w = confusion_matrix(eval_3w_df["planted_driver"], eval_3w_df["attributed_driver"], labels=drivers)
    cm_3w_df = pd.DataFrame(
        cm_3w,
        index=[f"Planted {d.capitalize()}" for d in drivers],
        columns=[f"Attributed {d.capitalize()}" for d in drivers],
    )

    acc_per_driver = {}
    for d in drivers:
        sub = eval_3w_df[eval_3w_df["planted_driver"] == d]
        acc_per_driver[d] = float((sub["attributed_driver"] == d).mean() * 100)

    # Secondary Report: Normalized SHAP
    shap_attr_3w = compute_normalized_shap_attribution(eval_3w_df, model)
    shap_acc_3w = float((pd.Series(shap_attr_3w, index=eval_3w_df.index) == eval_3w_df["planted_driver"]).mean() * 100)

    print("\n" + "=" * 80)
    print("  ATTRIBUTION BENCHMARK REPORT")
    print("=" * 80)
    print(f"Modality-Level Permutation Accuracy (First 3 Weeks, Observed Affect): {acc_3w:.2f}% (95% CI: [{ci_low:.2f}%, {ci_high:.2f}%])")
    print(f"Modality-Level Permutation Accuracy (All Crisis Rows):                 {acc_all:.2f}%")
    print(f"Chance Level (3 Modalities):                                           33.33%")
    print(f"Secondary Report (Normalized SHAP per Feature Count):                 {shap_acc_3w:.2f}%")
    print("\nAccuracy per Planted Driver:")
    for d in drivers:
        print(f"  - {d.capitalize()}: {acc_per_driver[d]:.2f}%")
    print("\n3x3 Confusion Matrix (Planted vs Attributed):")
    print(cm_3w_df.to_string())
    print("=" * 80)

    return {
        "metrics_table": metrics_table,
        "test_pos_rate": test_pos_rate,
        "acc_3w": acc_3w,
        "acc_all": acc_all,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "acc_per_driver": acc_per_driver,
        "cm_3w_df": cm_3w_df,
        "shap_acc_3w": shap_acc_3w,
    }


if __name__ == "__main__":
    main()
