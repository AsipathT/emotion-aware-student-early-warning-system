"""
Ablation study and withdrawal evidence evaluation for Component 2.
1. Evaluates feature-stream ablation on the test split:
   (a) clicks only
   (b) clicks + activity
   (c) clicks + activity + subs (full C2 model)
2. Computes withdrawal and failure supporting evidence across predicted trajectory classes.
3. Persists results to reports/metrics/ablation_evidence.json and prints formatted summaries.
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

from src.baselines import build_rule_inputs, rule_predict
from src.config import KEYS, component_root
from src.evaluate import evaluate
from src.features import build_causal_features, build_static_features
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

    print("Step 1: Loading datasets and constructing features...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)

    causal_df = build_causal_features(dense, labels)
    splits = make_splits(causal_df)

    train_c = splits["train"]
    test_c = splits["test"]
    y_train = train_c["label"]
    y_test = test_c["label"]

    print(f"  Train windows: {len(train_c):,}")
    print(f"  Test windows:  {len(test_c):,}")

    # Feature groups
    group_clicks = [
        "e_lag0",
        "e_lag1",
        "e_lag2",
        "e_lag3",
        "e_lag4",
        "e_lag5",
        "e_mean6",
        "e_sd6",
        "e_slope4",
        "e_recent_diff",
        "zero_weeks6",
        "zero_run",
        "week_t",
    ]
    group_activity = ["ad_lag0", "ad_mean3"]
    group_subs = ["subs_sum6", "delay_mean6"]

    streams = {
        "clicks": group_clicks,
        "clicks_activity": group_clicks + group_activity,
        "full": group_clicks + group_activity + group_subs,
    }

    print("\nStep 2: Training feature-stream ablations and evaluating on TEST...")
    ablation_results = {}
    c2_full_test_preds = None

    for name, cols in streams.items():
        print(f"  Fitting stream '{name}' ({len(cols)} features)...")
        clf = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            class_weight="balanced",
            random_state=42,
            early_stopping=False,
        )
        clf.fit(train_c[cols], y_train)
        preds = clf.predict(test_c[cols])
        ev = evaluate(y_test, preds)

        m_f1 = float(ev["macro_f1"])
        d_f1 = float(ev["per_class"]["declining"]["f1"])
        ablation_results[name] = {
            "macro_f1": m_f1,
            "declining_f1": d_f1,
        }
        print(f"    -> Macro-F1: {m_f1:.4f} | Declining F1: {d_f1:.4f}")

        if name == "full":
            c2_full_test_preds = preds

    print("\nStep 3: Evaluating baseline models for withdrawal supporting evidence...")
    # B1 Static Snapshot
    print("  Fitting B1 Static Snapshot baseline...")
    static_df = build_static_features(dense, labels)
    static_cols = [c for c in static_df.columns if c not in KEYS + ["week", "label"]]
    static_train = static_df.loc[train_c.index]
    static_test = static_df.loc[test_c.index]

    b1_clf = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=False,
    )
    b1_clf.fit(static_train[static_cols], y_train)
    b1_test_preds = b1_clf.predict(static_test[static_cols])

    # B2 Threshold Rule
    print("  Evaluating B2 Blackboard-like rule...")
    rule_df = build_rule_inputs(dense, labels)
    rule_test = rule_df.loc[test_c.index]
    b2_test_preds = rule_predict(rule_test["clicks_t"], rule_test["prior_mean"])

    # Obtain final_result for test windows
    test_merged = test_c[KEYS + ["week"]].merge(
        labels[KEYS + ["week", "final_result"]], on=KEYS + ["week"], how="left"
    )
    test_final_result = test_merged["final_result"].to_numpy()

    base_withdrawn_share = float(np.mean(test_final_result == "Withdrawn"))
    print(f"  Base Withdrawn Share on Test: {base_withdrawn_share * 100:.2f}%")

    model_predictions = {
        "c2_model": c2_full_test_preds,
        "b1_static": b1_test_preds,
        "b2_rule": b2_test_preds,
    }

    target_classes = ["declining", "improving", "stable", "volatile"]
    withdrawal_evidence = {}

    for m_name, m_preds in model_predictions.items():
        withdrawal_evidence[m_name] = {}
        for cls in target_classes:
            mask = m_preds == cls
            n = int(mask.sum())
            if n > 0:
                w_share = float(np.mean(test_final_result[mask] == "Withdrawn"))
                f_share = float(np.mean(test_final_result[mask] == "Fail"))
            else:
                w_share = 0.0
                f_share = 0.0
            withdrawal_evidence[m_name][cls] = {
                "withdrawn_share": w_share,
                "fail_share": f_share,
                "n": n,
            }

    print("\nStep 4: Saving reports/metrics/ablation_evidence.json...")
    metrics_dir = root / "reports" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    out_payload = {
        "ablation": ablation_results,
        "withdrawal_evidence": withdrawal_evidence,
        "base_withdrawn_share": base_withdrawn_share,
    }
    out_path = metrics_dir / "ablation_evidence.json"
    with open(out_path, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"  Saved: {out_path}")

    # Step 5: Print readable tables
    print("\n" + "=" * 70)
    print("FEATURE-STREAM ABLATION STUDY (ON TEST SPLIT)")
    print("=" * 70)
    print(f"{'Stream':<20} | {'Features':<10} | {'Macro-F1':<12} | {'Declining F1':<12}")
    print("-" * 70)
    for name, res in ablation_results.items():
        feat_count = len(streams[name])
        print(
            f"{name:<20} | {feat_count:<10} | {res['macro_f1']:<12.4f} | {res['declining_f1']:<12.4f}"
        )

    print("\n" + "=" * 75)
    print(f"WITHDRAWAL SUPPORTING EVIDENCE ON TEST (Base Withdrawn Rate: {base_withdrawn_share * 100:.2f}%)")
    print("=" * 75)
    for m_name, c_dict in withdrawal_evidence.items():
        print(f"\nModel: {m_name}")
        print(
            f"  {'Class':<12} | {'Windows (n)':<12} | {'Withdrawn Share':<17} | {'Fail Share':<12} | {'Risk (W+F)':<10}"
        )
        print("  " + "-" * 70)
        for cls, st in c_dict.items():
            w_pct = st["withdrawn_share"] * 100
            f_pct = st["fail_share"] * 100
            risk_pct = (st["withdrawn_share"] + st["fail_share"]) * 100
            print(
                f"  {cls:<12} | {st['n']:<12,} | {w_pct:>14.2f}% | {f_pct:>10.2f}% | {risk_pct:>8.2f}%"
            )
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
