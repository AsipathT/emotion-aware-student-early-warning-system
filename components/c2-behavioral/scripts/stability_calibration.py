"""
Temporal stability and confidence calibration analysis for Component 2 deploy model.
Evaluates prediction flip rates across consecutive weeks, multi-week probability smoothing,
Expected Calibration Error (ECE) with reliability diagram, and trajectory performance by academic term stage.
Offline analysis only; the deploy model is not retrained or modified.
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import KEYS, component_root
from src.deploy_features import to_deploy
from src.evaluate import evaluate
from src.features import build_causal_features
from src.splits import make_splits


def compute_consecutive_flip_rate(df: pd.DataFrame, label_col: str) -> tuple[float, int, int]:
    """
    Computes fraction of consecutive-week pairs where the label changes.
    Only pairs of consecutive academic weeks (week[i+1] == week[i] + 1) are evaluated.
    """
    groups = df.groupby(KEYS, sort=False)
    total_pairs = 0
    flips = 0
    for _, grp in groups:
        weeks = grp["week"].to_numpy()
        labels = grp[label_col].to_numpy()
        for i in range(len(weeks) - 1):
            if weeks[i + 1] == weeks[i] + 1:
                total_pairs += 1
                if labels[i + 1] != labels[i]:
                    flips += 1
    rate = flips / total_pairs if total_pairs > 0 else 0.0
    return float(rate), flips, total_pairs


def main() -> None:
    root = component_root()
    data_dir = root / "data"
    reports_dir = root / "reports"
    metrics_dir = reports_dir / "metrics"
    figures_dir = reports_dir / "figures"

    metrics_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("COMPONENT 2: TEMPORAL STABILITY AND CONFIDENCE CALIBRATION ANALYSIS")
    print("=" * 80)

    # 1. Load data and deploy model
    dense_path = data_dir / "weekly_dense.pkl"
    labels_path = data_dir / "labels.pkl"
    bundle_path = root / "models" / "c2_deploy.joblib"

    for p in [dense_path, labels_path, bundle_path]:
        if not p.is_file():
            print(f"ERROR: Missing input file: {p}")
            return

    print("Step 1: Loading test split and deploy model...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)

    causal_df = build_causal_features(dense, labels)
    splits = make_splits(causal_df)
    test_df = splits["test"]

    bundle = joblib.load(bundle_path)
    model = bundle["model"]
    features = bundle["features"]

    deploy_test = to_deploy(test_df)
    X_test = deploy_test[features]
    proba = model.predict_proba(X_test)
    classes = model.classes_

    pred_idx = np.argmax(proba, axis=1)
    pred_labels = classes[pred_idx]
    ref_labels = test_df["label"].to_numpy()

    eval_raw = evaluate(ref_labels, pred_labels)
    print(f"  Scored {len(test_df):,} test windows. Overall Macro-F1: {eval_raw['macro_f1']:.4f}")

    # Build student-sorted DataFrame
    df_scored = test_df[KEYS + ["week", "label"]].copy()
    df_scored["pred_label"] = pred_labels
    for i, c in enumerate(classes):
        df_scored[f"prob_{c}"] = proba[:, i]
    df_scored = df_scored.sort_values(KEYS + ["week"]).reset_index(drop=True)

    # 2. Consecutive Flip Rate
    print("\nStep 2: Calculating consecutive-week transition flip rates...")
    ref_flip_rate, ref_flips, total_pairs = compute_consecutive_flip_rate(df_scored, "label")
    pred_flip_rate, pred_flips, _ = compute_consecutive_flip_rate(df_scored, "pred_label")

    print("\n" + "-" * 70)
    print(f"{'Metric':<35} | {'Value':<15} | {'Flips / Pairs':<18}")
    print("-" * 70)
    print(f"{'Reference Ground Truth Flip Rate':<35} | {ref_flip_rate:<15.4f} | {ref_flips:,} / {total_pairs:,}")
    print(f"{'Model Prediction (Unsmoothed) Flip Rate':<35} | {pred_flip_rate:<15.4f} | {pred_flips:,} / {total_pairs:,}")
    print("-" * 70)

    # 3. Smoothing experiment (n = 1, 2, 3)
    print("\nStep 3: Multi-week probability smoothing (rolling mean over consecutive weeks)...")
    prob_cols = [f"prob_{c}" for c in classes]
    smoothing_results = {}

    diff_week = df_scored.groupby(KEYS)["week"].diff()
    is_break = (diff_week != 1) & (~diff_week.isna())
    streak_id = is_break.cumsum()

    print("\n" + "-" * 70)
    print(f"{'Smoothing Window (n)':<22} | {'Test Macro-F1':<16} | {'Flip Rate':<14} | {'Reduction'}")
    print("-" * 70)

    for n in [1, 2, 3]:
        smoothed_prob_df = (
            df_scored.groupby(KEYS + [streak_id])[prob_cols]
            .rolling(n, min_periods=1)
            .mean()
            .reset_index(drop=True)
        )
        smooth_arr = smoothed_prob_df.to_numpy()
        smooth_pred = classes[np.argmax(smooth_arr, axis=1)]

        n_eval = evaluate(df_scored["label"].to_numpy(), smooth_pred)
        n_macro_f1 = float(n_eval["macro_f1"])

        df_smooth = df_scored[KEYS + ["week"]].copy()
        df_smooth["smooth_pred"] = smooth_pred
        n_flip_rate, _, _ = compute_consecutive_flip_rate(df_smooth, "smooth_pred")

        red_str = "-" if n == 1 else f"{(n_flip_rate - pred_flip_rate) / pred_flip_rate * 100:.1f}%"
        print(f"{f'n = {n} week(s)':<22} | {n_macro_f1:<16.4f} | {n_flip_rate:<14.4f} | {red_str}")

        smoothing_results[str(n)] = {
            "macro_f1": round(n_macro_f1, 4),
            "flip_rate": round(n_flip_rate, 4),
        }
    print("-" * 70)

    # 4. Calibration & ECE
    print("\nStep 4: Reliability calibration and Expected Calibration Error (ECE)...")
    conf = np.max(proba, axis=1)
    correct = (pred_labels == ref_labels).astype(float)

    bin_edges = np.linspace(0.0, 1.0, 11)
    bins_info = []
    ece = 0.0

    print("\n" + "-" * 75)
    print(f"{'Bin':<6} | {'Range':<14} | {'Count (N)':<12} | {'Mean Conf':<12} | {'Accuracy':<12} | {'|Diff|':<8}")
    print("-" * 75)

    for b in range(10):
        low = bin_edges[b]
        high = bin_edges[b + 1]
        if b == 9:
            mask = (conf >= low) & (conf <= high)
        else:
            mask = (conf >= low) & (conf < high)

        n_b = int(np.sum(mask))
        if n_b > 0:
            mean_c = float(np.mean(conf[mask]))
            acc = float(np.mean(correct[mask]))
            diff = abs(acc - mean_c)
            ece += (n_b / len(conf)) * diff
        else:
            mean_c = 0.0
            acc = 0.0
            diff = 0.0

        bins_info.append(
            {
                "bin": b + 1,
                "bin_lower": round(float(low), 2),
                "bin_upper": round(float(high), 2),
                "n": n_b,
                "mean_confidence": round(mean_c, 4),
                "accuracy": round(acc, 4),
            }
        )
        print(f"{b+1:<6} | [{low:.1f}, {high:.1f}{']' if b == 9 else ')'} | {n_b:<12,d} | {mean_c:<12.4f} | {acc:<12.4f} | {diff:<8.4f}")

    print("-" * 75)
    mean_conf_all = float(np.mean(conf))
    acc_all = float(np.mean(correct))
    print(f"Overall Mean Confidence: {mean_conf_all:.4f}")
    print(f"Overall Accuracy:        {acc_all:.4f}")
    print(f"Expected Calibration Error (ECE): {ece:.4f}")

    # 5. Performance by Academic Week Bucket
    print("\nStep 5: Macro-F1 across academic term stages...")
    weeks = test_df["week"].to_numpy()
    buckets = [
        ("3-5", (weeks >= 3) & (weeks <= 5)),
        ("6-12", (weeks >= 6) & (weeks <= 12)),
        ("13+", weeks >= 13),
    ]
    bucket_results = {}
    print("\n" + "-" * 60)
    print(f"{'Academic Term Stage':<25} | {'Windows':<15} | {'Macro-F1':<12}")
    print("-" * 60)
    for b_name, b_mask in buckets:
        sub_ref = ref_labels[b_mask]
        sub_pred = pred_labels[b_mask]
        sub_eval = evaluate(sub_ref, sub_pred)
        b_f1 = float(sub_eval["macro_f1"])
        bucket_results[b_name] = round(b_f1, 4)
        print(f"{f'Weeks {b_name}':<25} | {len(sub_ref):<15,d} | {b_f1:<12.4f}")
    print("-" * 60)

    # 6. Save JSON Metrics
    out_payload = {
        "flip_rate": {
            "reference": round(ref_flip_rate, 4),
            "predicted": round(pred_flip_rate, 4),
        },
        "smoothing": smoothing_results,
        "calibration": {
            "ece": round(ece, 4),
            "mean_confidence": round(mean_conf_all, 4),
            "accuracy": round(acc_all, 4),
            "bins": bins_info,
        },
        "macro_f1_by_week_bucket": bucket_results,
    }
    metrics_file = metrics_dir / "stability_calibration.json"
    with open(metrics_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"\nSaved metrics: {metrics_file}")

    # 7. Generate Figure 5: Reliability Diagram
    fig_path = figures_dir / "fig5_reliability.png"
    plt.figure(figsize=(7, 6))

    # Perfect calibration diagonal
    plt.plot([0, 1], [0, 1], "k--", label="Perfect Calibration", linewidth=1.5, alpha=0.7)

    # Filter non-empty bins for curve
    valid_bins = [b for b in bins_info if b["n"] > 0]
    bin_confs = [b["mean_confidence"] for b in valid_bins]
    bin_accs = [b["accuracy"] for b in valid_bins]

    # Bar diagram with line
    plt.plot(bin_confs, bin_accs, marker="s", color="#2563eb", linewidth=2, markersize=7, label=f"Deploy Model (ECE = {ece:.3f})")
    plt.bar(
        [0.5 * (b["bin_lower"] + b["bin_upper"]) for b in valid_bins],
        bin_accs,
        width=0.08,
        alpha=0.25,
        color="#3b82f6",
        edgecolor="#1d4ed8",
        label="Bin Accuracy",
    )

    plt.xlabel("Confidence (Predicted Probability)", fontsize=11, fontweight="bold")
    plt.ylabel("Observed Empirical Accuracy", fontsize=11, fontweight="bold")
    plt.title("Reliability Diagram: Confidence Calibration (C2 Deploy Model)", fontsize=12, fontweight="bold", pad=12)
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left", frameon=True, fontsize=10)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150)
    plt.close()
    print(f"Saved figure:  {fig_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
