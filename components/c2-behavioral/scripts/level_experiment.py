"""
Offline experiment, not deployed; decision rule: adopt in v2 only if val gain >= 0.01 and test does not drop.

Evaluates adding two expanding cumulative baseline level features (lvl and lvlmax)
to the scale-free deployment feature set to assess personalization benefits against absolute click volume.
"""

import json
import sys
from pathlib import Path

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import numpy as np
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
    reports_dir = root / "reports"
    metrics_dir = reports_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("COMPONENT 2: OFFLINE LEVEL FEATURE EXPERIMENT")
    print("=" * 80)
    print("Decision rule: adopt in v2 only if val gain >= 0.01 and test does not drop\n")

    dense_path = data_dir / "weekly_dense.pkl"
    labels_path = data_dir / "labels.pkl"

    for p in [dense_path, labels_path]:
        if not p.is_file():
            print(f"ERROR: Missing input file: {p}")
            return

    # 1. Load data and extract causal features
    print("Step 1: Loading weekly dense and label records...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)

    print("  Building causal features...")
    causal_df = build_causal_features(dense, labels)

    # 2. Compute level features from weekly_dense
    print("  Computing student-level expanding baseline features (cum_mean, cum_max)...")
    dense_sorted = dense.sort_values(KEYS + ["week"]).copy()
    dense_sorted["e"] = np.log1p(dense_sorted["clicks"].astype(float))
    grouped = dense_sorted.groupby(KEYS)["e"]

    dense_sorted["cum_mean"] = grouped.expanding().mean().reset_index(level=list(range(len(KEYS))), drop=True)
    dense_sorted["cum_max"] = grouped.expanding().max().reset_index(level=list(range(len(KEYS))), drop=True)

    dense_sub = dense_sorted[KEYS + ["week", "cum_mean", "cum_max"]]
    causal_merged = causal_df.merge(dense_sub, on=KEYS + ["week"], how="left")
    causal_merged["lvl"] = causal_merged["e_lag0"] - causal_merged["cum_mean"]
    causal_merged["lvlmax"] = causal_merged["e_lag0"] - causal_merged["cum_max"]

    # 3. Create dataset splits
    print("\nStep 2: Partitioning dataset into train, val, and test splits...")
    splits = make_splits(causal_merged)
    train_df = splits["train"]
    val_df = splits["val"]
    test_df = splits["test"]

    print(f"  Train: {len(train_df):,} windows")
    print(f"  Val:   {len(val_df):,} windows")
    print(f"  Test:  {len(test_df):,} windows")

    train_deploy = to_deploy(train_df)
    val_deploy = to_deploy(val_df)
    test_deploy = to_deploy(test_df)

    # Attach lvl and lvlmax to deploy DataFrames
    for df_target, df_source in [(train_deploy, train_df), (val_deploy, val_df), (test_deploy, test_df)]:
        df_target["lvl"] = df_source["lvl"].to_numpy()
        df_target["lvlmax"] = df_source["lvlmax"].to_numpy()

    # 4. Model A: Baseline Deploy Features (14 features)
    print("\nStep 3: Training Baseline Model (14 scale-free DEPLOY_FEATURES)...")
    clf_base = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    clf_base.fit(train_deploy[DEPLOY_FEATURES], train_deploy["label"])

    pred_val_base = clf_base.predict(val_deploy[DEPLOY_FEATURES])
    pred_test_base = clf_base.predict(test_deploy[DEPLOY_FEATURES])
    f1_val_base = float(evaluate(val_deploy["label"], pred_val_base)["macro_f1"])
    f1_test_base = float(evaluate(test_deploy["label"], pred_test_base)["macro_f1"])

    # 5. Model B: Deploy Features + Level Features (16 features)
    lvl_features = DEPLOY_FEATURES + ["lvl", "lvlmax"]
    print("Step 4: Training Level-Augmented Model (16 features: DEPLOY_FEATURES + lvl + lvlmax)...")
    clf_lvl = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    clf_lvl.fit(train_deploy[lvl_features], train_deploy["label"])

    pred_val_lvl = clf_lvl.predict(val_deploy[lvl_features])
    pred_test_lvl = clf_lvl.predict(test_deploy[lvl_features])
    f1_val_lvl = float(evaluate(val_deploy["label"], pred_val_lvl)["macro_f1"])
    f1_test_lvl = float(evaluate(test_deploy["label"], pred_test_lvl)["macro_f1"])

    # 6. Evaluation Deltas & Decision Rule
    delta_val = f1_val_lvl - f1_val_base
    delta_test = f1_test_lvl - f1_test_base

    # Decision rule evaluation
    val_criterion = delta_val >= 0.01
    test_criterion = delta_test >= 0.0
    recommendation = "ADOPT IN V2" if (val_criterion and test_criterion) else "DO NOT ADOPT"

    print("\n" + "=" * 70)
    print("LEVEL EXPERIMENT EVALUATION RESULTS")
    print("=" * 70)
    print(f"{'Configuration':<32} | {'Val Macro-F1':<16} | {'Test Macro-F1':<16}")
    print("-" * 70)
    print(f"{'Baseline (14 deploy features)':<32} | {f1_val_base:<16.4f} | {f1_test_base:<16.4f}")
    print(f"{'With Level (16 features)':<32} | {f1_val_lvl:<16.4f} | {f1_test_lvl:<16.4f}")
    print("-" * 70)
    print(f"{'Delta (With Level - Baseline)':<32} | {delta_val:<+16.4f} | {delta_test:<+16.4f}")
    print("=" * 70)
    print(f"Decision Rule Status: Val Gain ({delta_val:+.4f} >= +0.0100: {val_criterion}), Test Drop ({delta_test:+.4f} >= 0.0000: {test_criterion})")
    print(f"Outcome: {recommendation}\n")

    # 7. Persist metrics
    out_payload = {
        "baseline": {
            "val": round(f1_val_base, 4),
            "test": round(f1_test_base, 4),
        },
        "with_level": {
            "val": round(f1_val_lvl, 4),
            "test": round(f1_test_lvl, 4),
        },
        "delta": {
            "val": round(delta_val, 4),
            "test": round(delta_test, 4),
        },
    }

    metrics_file = metrics_dir / "level_experiment.json"
    with open(metrics_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"Saved metrics: {metrics_file}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
