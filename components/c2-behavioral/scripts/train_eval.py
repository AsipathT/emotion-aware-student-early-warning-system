"""
Training and evaluation pipeline for Component 2 (Behavioral Engagement Trajectory).
Orchestrates:
1. Feature extraction for causal, static, and heuristic rule inputs.
2. Presentation-temporal train/val/test splitting.
3. 5-fold student-grouped cross-validation on train for the C2 causal model.
4. Model fitting: Majority baseline, B1 static snapshot, B2 threshold rule, and C2 causal model.
5. Multi-metric evaluation on val and test splits.
6. Breakdown by course module on the test set.
7. Artifact persistence (c2_model.joblib and model_eval.json).
"""

import json
import sys
from pathlib import Path

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold

from src.baselines import MajorityBaseline, build_rule_inputs, rule_predict
from src.config import KEYS, component_root
from src.evaluate import evaluate
from src.features import build_causal_features, build_static_features
from src.splits import make_splits, split_report


def main() -> None:
    root = component_root()
    data_dir = root / "data"

    labels_path = data_dir / "labels.pkl"
    dense_path = data_dir / "weekly_dense.pkl"
    enrolment_path = data_dir / "enrolment.pkl"

    for p in [labels_path, dense_path, enrolment_path]:
        if not p.is_file():
            print(f"ERROR: Required input file missing: {p}")
            return

    print("Step 1: Loading pickle datasets...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)
    enrolment = pd.read_pickle(enrolment_path)
    print(f"  Loaded weekly_dense: {len(dense):,} rows")
    print(f"  Loaded labels:       {len(labels):,} rows")
    print(f"  Loaded enrolment:    {len(enrolment):,} rows")

    print("\nBuilding causal features, static features, and rule inputs...")
    causal_df = build_causal_features(dense, labels)
    static_df = build_static_features(dense, labels)
    rule_df = build_rule_inputs(dense, labels)

    assert len(causal_df) == len(static_df) == len(rule_df), "Length mismatch across feature frames"
    assert (causal_df[KEYS] == static_df[KEYS]).all().all(), "KEYS mismatch causal vs static"
    assert (causal_df[KEYS] == rule_df[KEYS]).all().all(), "KEYS mismatch causal vs rule"
    assert (causal_df["week"] == static_df["week"]).all(), "week mismatch causal vs static"
    assert (causal_df["week"] == rule_df["week"]).all(), "week mismatch causal vs rule"
    assert (causal_df["label"] == static_df["label"]).all(), "label mismatch causal vs static"
    assert (causal_df["label"] == rule_df["label"]).all(), "label mismatch causal vs rule"
    print(f"  Aligned {len(causal_df):,} non-dormant label rows across all feature representations.")

    print("\nStep 2: Splitting dataset into train, val, test...")
    splits_c = make_splits(causal_df)
    rep = split_report(causal_df, splits_c)

    print("\n" + "=" * 65)
    print("DATASET SPLIT REPORT")
    print("=" * 65)
    print(f"  Train windows: {rep['train']['windows']:,} (distinct students: {rep['train']['distinct_students']:,})")
    print(f"  Val windows:   {rep['val']['windows']:,} (distinct students: {rep['val']['distinct_students']:,}, removed: {rep['removed_val']:,})")
    print(f"  Test windows:  {rep['test']['windows']:,} (distinct students: {rep['test']['distinct_students']:,}, removed: {rep['removed_test']:,})")
    print("=" * 65)

    train_idx = splits_c["train"].index
    val_idx = splits_c["val"].index
    test_idx = splits_c["test"].index

    static_train = static_df.loc[train_idx]
    static_val = static_df.loc[val_idx]
    static_test = static_df.loc[test_idx]

    rule_train = rule_df.loc[train_idx]
    rule_val = rule_df.loc[val_idx]
    rule_test = rule_df.loc[test_idx]

    causal_cols = [c for c in causal_df.columns if c not in KEYS + ["week", "label"]]
    static_cols = [c for c in static_df.columns if c not in KEYS + ["week", "label"]]

    X_train_c = splits_c["train"][causal_cols]
    y_train = splits_c["train"]["label"]
    X_val_c = splits_c["val"][causal_cols]
    y_val = splits_c["val"]["label"]
    X_test_c = splits_c["test"][causal_cols]
    y_test = splits_c["test"]["label"]

    X_train_s = static_train[static_cols]
    X_val_s = static_val[static_cols]
    X_test_s = static_test[static_cols]

    print("\nStep 3 & 4: 5-Fold GroupKFold Cross-Validation on Train for C2 Model...")
    gkf = GroupKFold(n_splits=5)
    train_groups = splits_c["train"]["id_student"]
    cv_f1s = []

    for fold, (tr_i, va_i) in enumerate(gkf.split(X_train_c, y_train, groups=train_groups), start=1):
        cv_clf = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            class_weight="balanced",
            random_state=42,
            early_stopping=False,
        )
        cv_clf.fit(X_train_c.iloc[tr_i], y_train.iloc[tr_i])
        fold_pred = cv_clf.predict(X_train_c.iloc[va_i])
        fold_f1 = float(f1_score(y_train.iloc[va_i], fold_pred, average="macro", zero_division=0))
        cv_f1s.append(fold_f1)
        print(f"  Fold {fold}: Macro-F1 = {fold_f1:.4f}")

    cv_macro_f1 = {
        "folds": cv_f1s,
        "mean": float(np.mean(cv_f1s)),
        "std": float(np.std(cv_f1s)),
    }
    print(f"  CV Macro-F1 Mean: {cv_macro_f1['mean']:.4f} (+/- {cv_macro_f1['std']:.4f})")

    print("\nStep 5: Training full models and evaluating baselines...")
    # 1. Majority
    majority = MajorityBaseline().fit(y_train)
    maj_pred_val = majority.predict(len(y_val))
    maj_pred_test = majority.predict(len(y_test))
    eval_maj_val = evaluate(y_val, maj_pred_val)
    eval_maj_test = evaluate(y_test, maj_pred_test)

    # 2. B1 Static Snapshot
    print("  Fitting B1 Static Snapshot classifier...")
    b1_static = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    b1_static.fit(X_train_s, y_train)
    s_pred_val = b1_static.predict(X_val_s)
    s_pred_test = b1_static.predict(X_test_s)
    eval_s_val = evaluate(y_val, s_pred_val)
    eval_s_test = evaluate(y_test, s_pred_test)

    # 3. B2 Heuristic Rule
    print("  Evaluating B2 Blackboard-like rule...")
    r_pred_val = rule_predict(rule_val["clicks_t"], rule_val["prior_mean"])
    r_pred_test = rule_predict(rule_test["clicks_t"], rule_test["prior_mean"])
    eval_r_val = evaluate(y_val, r_pred_val)
    eval_r_test = evaluate(y_test, r_pred_test)

    # 4. C2 Causal Model
    print("  Fitting C2 Causal Trajectory classifier...")
    c2_model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    c2_model.fit(X_train_c, y_train)
    c_pred_val = c2_model.predict(X_val_c)
    c_pred_test = c2_model.predict(X_test_c)
    eval_c_val = evaluate(y_val, c_pred_val)
    eval_c_test = evaluate(y_test, c_pred_test)

    print("\nStep 6: Breakdown by code_module on Test Set...")
    test_mods = sorted(splits_c["test"]["code_module"].unique())
    test_by_module = {"c2_model": {}, "b1_static": {}}
    test_mod_arr = splits_c["test"]["code_module"].to_numpy()
    y_test_arr = y_test.to_numpy()

    for mod in test_mods:
        m_mask = test_mod_arr == mod
        n_w = int(m_mask.sum())
        f1_c = float(f1_score(y_test_arr[m_mask], c_pred_test[m_mask], average="macro", zero_division=0))
        f1_s = float(f1_score(y_test_arr[m_mask], s_pred_test[m_mask], average="macro", zero_division=0))
        test_by_module["c2_model"][mod] = {"macro_f1": f1_c, "n_windows": n_w}
        test_by_module["b1_static"][mod] = {"macro_f1": f1_s, "n_windows": n_w}

    print("\nStep 7: Saving artifacts...")
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib_path = models_dir / "c2_model.joblib"
    joblib.dump(c2_model, joblib_path)
    print(f"  Saved model: {joblib_path}")

    metrics_dir = root / "reports" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = metrics_dir / "model_eval.json"
    eval_payload = {
        "split_report": rep,
        "cv_macro_f1": cv_macro_f1,
        "results": {
            "majority": {"val": eval_maj_val, "test": eval_maj_test},
            "b1_static": {"val": eval_s_val, "test": eval_s_test},
            "b2_rule": {"val": eval_r_val, "test": eval_r_test},
            "c2_model": {"val": eval_c_val, "test": eval_c_test},
        },
        "test_by_module": test_by_module,
    }
    with open(metrics_file, "w") as f:
        json.dump(eval_payload, f, indent=2)
    print(f"  Saved metrics: {metrics_file}")

    print("\n" + "=" * 75)
    print("STEP 8: SUMMARY EVALUATION RESULTS")
    print("=" * 75)
    print(f"{'Model':<15} | {'Val Macro-F1':<12} | {'Val Acc':<10} | {'Test Macro-F1':<14} | {'Test Acc':<10}")
    print("-" * 75)
    for name, r_dict in [
        ("majority", eval_payload["results"]["majority"]),
        ("b1_static", eval_payload["results"]["b1_static"]),
        ("b2_rule", eval_payload["results"]["b2_rule"]),
        ("c2_model", eval_payload["results"]["c2_model"]),
    ]:
        v_f1 = r_dict["val"]["macro_f1"]
        v_acc = r_dict["val"]["accuracy"]
        t_f1 = r_dict["test"]["macro_f1"]
        t_acc = r_dict["test"]["accuracy"]
        print(f"{name:<15} | {v_f1:<12.4f} | {v_acc:<10.4f} | {t_f1:<14.4f} | {t_acc:<10.4f}")

    print("\n" + "-" * 75)
    print("C2 MODEL PER-CLASS METRICS ON TEST:")
    print("-" * 75)
    print(f"{'Class':<12} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<10}")
    print("-" * 75)
    for lbl, pc in eval_c_test["per_class"].items():
        print(f"{lbl:<12} | {pc['precision']:<10.4f} | {pc['recall']:<10.4f} | {pc['f1']:<10.4f} | {pc['support']:<10,}")

    print("\n" + "-" * 75)
    print("TEST MACRO-F1 BY MODULE (LEAVE-CCC-OUT CHECK):")
    print("-" * 75)
    print(f"{'Module':<10} | {'Windows':<10} | {'C2 Model F1':<15} | {'B1 Static F1':<15}")
    print("-" * 75)
    for mod in test_mods:
        c_f1 = test_by_module["c2_model"][mod]["macro_f1"]
        s_f1 = test_by_module["b1_static"][mod]["macro_f1"]
        nw = test_by_module["c2_model"][mod]["n_windows"]
        print(f"{mod:<10} | {nw:<10,} | {c_f1:<15.4f} | {s_f1:<15.4f}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
