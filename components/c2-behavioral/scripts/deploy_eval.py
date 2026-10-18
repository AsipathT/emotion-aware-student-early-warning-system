"""
Deployment evaluation and scale robustness pipeline for Component 2.
1. Trains deploy model on scale-free features (to_deploy) of train split.
2. Evaluates deploy model on val and test splits.
3. Performs scale robustness test by 3x scaling raw clicks on test split.
4. Compares deploy model vs. full model under scale shift.
5. Saves models/c2_deploy.joblib and reports/metrics/deploy_eval.json.
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
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src.config import KEYS, component_root
from src.deploy_features import DEPLOY_FEATURES, to_deploy
from src.evaluate import evaluate
from src.features import build_causal_features
from src.splits import make_splits


def main() -> None:
    root = component_root()
    data_dir = root / "data"

    dense_path = data_dir / "weekly_dense.pkl"
    labels_path = data_dir / "labels.pkl"

    for p in [dense_path, labels_path]:
        if not p.is_file():
            print(f"ERROR: Missing input file: {p}")
            return

    print("Step 1: Building unscaled causal features and dataset splits...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)

    causal_df = build_causal_features(dense, labels)
    splits = make_splits(causal_df)

    train_c = splits["train"]
    val_c = splits["val"]
    test_c = splits["test"]

    print(f"  Train windows: {len(train_c):,}")
    print(f"  Val windows:   {len(val_c):,}")
    print(f"  Test windows:  {len(test_c):,}")

    train_deploy = to_deploy(train_c)
    val_deploy = to_deploy(val_c)
    test_deploy = to_deploy(test_c)

    print("\nTraining deploy model on scale-free DEPLOY_FEATURES...")
    deploy_model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    deploy_model.fit(train_deploy[DEPLOY_FEATURES], train_deploy["label"])

    print("Evaluating deploy model on val and test...")
    val_preds = deploy_model.predict(val_deploy[DEPLOY_FEATURES])
    test_preds = deploy_model.predict(test_deploy[DEPLOY_FEATURES])

    eval_deploy_val = evaluate(val_deploy["label"], val_preds)
    eval_deploy_test = evaluate(test_deploy["label"], test_preds)
    deploy_unscaled_macro_f1 = float(eval_deploy_test["macro_f1"])

    print(f"  Deploy Model Val Macro-F1:  {eval_deploy_val['macro_f1']:.4f}")
    print(f"  Deploy Model Test Macro-F1: {eval_deploy_test['macro_f1']:.4f}")

    print("\nStep 2: SCALE TEST (3x raw clicks on test split)...")
    scaled_dense = dense.copy()
    scaled_dense["clicks"] = (scaled_dense["clicks"] * 3).astype(int)

    scaled_causal_df = build_causal_features(scaled_dense, labels)
    scaled_splits = make_splits(scaled_causal_df)
    scaled_test_causal = scaled_splits["test"]
    assert len(scaled_test_causal) == 204607, f"Expected 204,607 test windows, got {len(scaled_test_causal)}"

    scaled_test_deploy = to_deploy(scaled_test_causal)
    scaled_deploy_preds = deploy_model.predict(scaled_test_deploy[DEPLOY_FEATURES])
    eval_deploy_scaled = evaluate(scaled_test_deploy["label"], scaled_deploy_preds)
    deploy_macro_f1 = float(eval_deploy_scaled["macro_f1"])

    # Full model evaluation
    full_model_path = root / "models" / "c2_model.joblib"
    full_features = [c for c in causal_df.columns if c not in KEYS + ["week", "label"]]

    if full_model_path.is_file():
        print(f"  Loading existing full model from {full_model_path}...")
        full_model = joblib.load(full_model_path)
    else:
        print("  Retraining full model on unscaled train...")
        full_model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            class_weight="balanced",
            random_state=42,
            early_stopping=False,
        )
        full_model.fit(train_c[full_features], train_c["label"])

    unscaled_full_preds = full_model.predict(test_c[full_features])
    eval_full_unscaled = evaluate(test_c["label"], unscaled_full_preds)
    full_unscaled_macro_f1 = float(eval_full_unscaled["macro_f1"])

    scaled_full_preds = full_model.predict(scaled_test_causal[full_features])
    eval_full_scaled = evaluate(scaled_test_causal["label"], scaled_full_preds)
    full_macro_f1 = float(eval_full_scaled["macro_f1"])

    print(f"  Full Model Unscaled Test Macro-F1: {full_unscaled_macro_f1:.4f}")
    print(f"  Full Model Scaled (3x) Test Macro-F1: {full_macro_f1:.4f}")
    print(f"  Deploy Model Scaled (3x) Test Macro-F1: {deploy_macro_f1:.4f}")

    print("\nStep 3: Saving artifacts...")
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    deploy_bundle = {
        "model": deploy_model,
        "features": DEPLOY_FEATURES,
        "version": "c2-deploy-1",
    }
    deploy_joblib_path = models_dir / "c2_deploy.joblib"
    joblib.dump(deploy_bundle, deploy_joblib_path)
    print(f"  Saved bundle: {deploy_joblib_path}")

    metrics_dir = root / "reports" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    out_payload = {
        "deploy": {
            "val": eval_deploy_val,
            "test": eval_deploy_test,
        },
        "scale_test": {
            "deploy_macro_f1": deploy_macro_f1,
            "full_macro_f1": full_macro_f1,
            "deploy_unscaled_macro_f1": deploy_unscaled_macro_f1,
            "full_unscaled_macro_f1": full_unscaled_macro_f1,
        },
    }
    metrics_file = metrics_dir / "deploy_eval.json"
    with open(metrics_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"  Saved metrics: {metrics_file}")

    # Step 4: Summary table
    print("\n" + "=" * 75)
    print("DEPLOY MODEL EVALUATION RESULTS")
    print("=" * 75)
    print(f"{'Split':<10} | {'Macro-F1':<12} | {'Accuracy':<10}")
    print("-" * 75)
    print(f"{'Val':<10} | {eval_deploy_val['macro_f1']:<12.4f} | {eval_deploy_val['accuracy']:<10.4f}")
    print(f"{'Test':<10} | {eval_deploy_test['macro_f1']:<12.4f} | {eval_deploy_test['accuracy']:<10.4f}")

    print("\n" + "-" * 75)
    print("DEPLOY MODEL PER-CLASS TEST METRICS:")
    print("-" * 75)
    print(f"{'Class':<12} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<10}")
    print("-" * 75)
    for lbl, pc in eval_deploy_test["per_class"].items():
        print(f"{lbl:<12} | {pc['precision']:<10.4f} | {pc['recall']:<10.4f} | {pc['f1']:<10.4f} | {pc['support']:<10,}")

    print("\n" + "=" * 75)
    print("SCALE ROBUSTNESS TEST (Clicks multiplied by 3x)")
    print("=" * 75)
    print(f"{'Model':<15} | {'Unscaled Test F1':<18} | {'Scaled (3x) Test F1':<20} | {'Delta':<10}")
    print("-" * 75)
    deploy_delta = deploy_macro_f1 - deploy_unscaled_macro_f1
    full_delta = full_macro_f1 - full_unscaled_macro_f1
    print(f"{'deploy':<15} | {deploy_unscaled_macro_f1:<18.4f} | {deploy_macro_f1:<20.4f} | {deploy_delta:<+10.4f}")
    print(f"{'full (c2_model)':<15} | {full_unscaled_macro_f1:<18.4f} | {full_macro_f1:<20.4f} | {full_delta:<+10.4f}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
