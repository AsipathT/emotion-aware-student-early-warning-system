"""
scripts/export_samples.py

Exports sample trajectory prediction envelopes and computes confidence quantiles:
  1. Loads labels.pkl and weekly_dense.pkl, builds causal features, partitions TEST split.
  2. Applies deploy model (c2_deploy.joblib) to predict probabilities, labels, and confidence.
  3. Computes contributing indicators using raw causal feature columns.
  4. Generates synthetic PIDs (STU_<sha256[:8]>).
  5. Stratified samples 200 rows (up to 50 per class) + 5 hand-made dormancy-rule records.
  6. Validates every record with TrajectoryRecord and builds standard envelope.
  7. Computes confidence quantiles on the full test split and saves metrics.
"""

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure components/c2-behavioral root is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import joblib
import numpy as np
import pandas as pd

from service.schemas import TrajectoryRecord, build_envelope
from src.config import DORMANT_RULE_CONFIDENCE, component_root
from src.deploy_features import to_deploy
from src.features import build_causal_features
from src.indicators import contributing_indicators
from src.splits import make_splits


def make_pid(code_module: str, code_presentation: str, id_student: Any) -> str:
    """
    Generates a synthetic, deterministic student PID:
    'STU_' followed by the first 8 hex characters of sha256(module_presentation_student).
    """
    key_str = f"{code_module}_{code_presentation}_{id_student}"
    hash_hex = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return f"STU_{hash_hex[:8]}"


def build_dormant_records() -> List[TrajectoryRecord]:
    """Generates 5 hand-made dormancy-rule records for testing and demonstration."""
    records: List[TrajectoryRecord] = []
    dormant_specs = [
        ("AAA", "2014J", "9900001", 7, ["no_activity_7w"]),
        ("BBB", "2014J", "9900002", 8, ["no_activity_7w"]),
        ("CCC", "2014J", "9900003", 9, ["never_active"]),
        ("DDD", "2014J", "9900004", 10, ["no_activity_7w"]),
        ("EEE", "2014J", "9900005", 11, ["never_active"]),
    ]
    for mod, pres, stu, wk, inds in dormant_specs:
        records.append(
            TrajectoryRecord(
                pid=make_pid(mod, pres, stu),
                course_id=f"{mod}_{pres}",
                week_index=wk,
                trajectory_label="declining",
                confidence=float(DORMANT_RULE_CONFIDENCE),
                contributing_indicators=inds,
            )
        )
    return records


def sample_stratified(
    df: pd.DataFrame,
    label_col: str = "predicted_label",
    n_per_class: int = 50,
    random_state: int = 42,
) -> pd.DataFrame:
    """Stratified sample with up to n_per_class rows per label."""
    sampled_dfs = []
    for label in sorted(df[label_col].unique()):
        group = df.loc[df[label_col] == label]
        n_sample = min(n_per_class, len(group))
        sampled_dfs.append(group.sample(n=n_sample, random_state=random_state))
    return pd.concat(sampled_dfs, ignore_index=True)


def compute_confidence_quantiles(
    pred_labels: np.ndarray, confidences: np.ndarray
) -> Dict[str, Dict[str, float]]:
    """
    Computes min, 5, 25, 50, 75, 95, 99 percentiles, max, and mean confidence
    per predicted label, plus an overall aggregate.
    """
    quantiles_data: Dict[str, Dict[str, float]] = {}
    labels = sorted(list(set(pred_labels)))
    for lbl in labels:
        lbl_confs = confidences[pred_labels == lbl]
        pcts = np.percentile(lbl_confs, [5, 25, 50, 75, 95, 99])
        quantiles_data[lbl] = {
            "count": int(len(lbl_confs)),
            "min": float(np.min(lbl_confs)),
            "p05": float(pcts[0]),
            "p25": float(pcts[1]),
            "p50": float(pcts[2]),
            "p75": float(pcts[3]),
            "p95": float(pcts[4]),
            "p99": float(pcts[5]),
            "max": float(np.max(lbl_confs)),
            "mean": float(np.mean(lbl_confs)),
        }

    overall_pcts = np.percentile(confidences, [5, 25, 50, 75, 95, 99])
    quantiles_data["overall"] = {
        "count": int(len(confidences)),
        "min": float(np.min(confidences)),
        "p05": float(overall_pcts[0]),
        "p25": float(overall_pcts[1]),
        "p50": float(overall_pcts[2]),
        "p75": float(overall_pcts[3]),
        "p95": float(overall_pcts[4]),
        "p99": float(overall_pcts[5]),
        "max": float(np.max(confidences)),
        "mean": float(np.mean(confidences)),
    }
    return quantiles_data


def main() -> None:
    root = component_root()
    data_dir = root / "data"
    models_dir = root / "models"
    reports_dir = root / "reports"
    samples_dir = reports_dir / "samples"
    metrics_dir = reports_dir / "metrics"

    samples_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    dense_path = data_dir / "weekly_dense.pkl"
    labels_path = data_dir / "labels.pkl"
    bundle_path = models_dir / "c2_deploy.joblib"

    print("Step 1: Loading data and building causal features...")
    dense = pd.read_pickle(dense_path)
    labels = pd.read_pickle(labels_path)
    causal_df = build_causal_features(dense, labels)
    splits = make_splits(causal_df)
    test_split = splits["test"].copy().reset_index(drop=True)
    print(f"  Test split size: {len(test_split):,} rows")

    print("Step 2: Loading deploy bundle and scoring test split...")
    bundle = joblib.load(bundle_path)
    model = bundle["model"]
    deploy_features = bundle["features"]

    test_deploy = to_deploy(test_split)
    X_test = test_deploy[deploy_features]
    proba = model.predict_proba(X_test)
    classes = np.array(model.classes_)
    argmax_idx = np.argmax(proba, axis=1)
    pred_labels = classes[argmax_idx]
    confidences = np.max(proba, axis=1)

    # Attach prediction outputs to test dataframe
    test_scored = test_split.assign(
        predicted_label=pred_labels,
        confidence=confidences,
    )

    print("Step 3: Computing confidence quantiles on full test split...")
    quantiles = compute_confidence_quantiles(pred_labels, confidences)
    quantiles_path = metrics_dir / "confidence_quantiles.json"
    with open(quantiles_path, "w", encoding="utf-8") as f:
        json.dump(quantiles, f, indent=2)
    print(f"  Saved quantiles: {quantiles_path.relative_to(root)}")

    # Print confidence quantiles table
    print("\n" + "=" * 94)
    print("CONFIDENCE QUANTILES ON WHOLE TEST SPLIT (Uncalibrated Max Probability)")
    print("=" * 94)
    print(f"{'Label':<12} | {'Count':<8} | {'Min':<6} | {'P05':<6} | {'P25':<6} | {'P50':<6} | {'P75':<6} | {'P95':<6} | {'P99':<6} | {'Max':<6} | {'Mean':<6}")
    print("-" * 94)
    for lbl, stats in quantiles.items():
        print(
            f"{lbl:<12} | {stats['count']:<8,} | {stats['min']:<6.4f} | {stats['p05']:<6.4f} | "
            f"{stats['p25']:<6.4f} | {stats['p50']:<6.4f} | {stats['p75']:<6.4f} | "
            f"{stats['p95']:<6.4f} | {stats['p99']:<6.4f} | {stats['max']:<6.4f} | {stats['mean']:<6.4f}"
        )
    print("=" * 94 + "\n")

    print("Step 4: Stratified sampling 200 rows (up to 50 per class)...")
    sampled_df = sample_stratified(test_scored, label_col="predicted_label", n_per_class=50, random_state=42)
    print(f"  Sampled {len(sampled_df)} prediction rows across classes:")
    for lbl, count in sampled_df["predicted_label"].value_counts().items():
        print(f"    {lbl}: {count}")

    print("Step 5: Building validated TrajectoryRecord objects...")
    validated_records: List[TrajectoryRecord] = []
    for _, row in sampled_df.iterrows():
        raw_row_dict = row.to_dict()
        label = str(row["predicted_label"])
        indicators = contributing_indicators(raw_row_dict, label)
        pid = make_pid(row["code_module"], row["code_presentation"], row["id_student"])
        course_id = f"{row['code_module']}_{row['code_presentation']}"
        week_index = int(row["week"])
        confidence = float(row["confidence"])

        record = TrajectoryRecord(
            pid=pid,
            course_id=course_id,
            week_index=week_index,
            trajectory_label=label,
            confidence=confidence,
            contributing_indicators=indicators,
        )
        validated_records.append(record)

    dormant_records = build_dormant_records()
    print(f"  Added {len(dormant_records)} hand-made dormancy-rule records.")
    validated_records.extend(dormant_records)

    total_records = len(validated_records)
    print(f"  Total validated records: {total_records}")
    assert total_records == 205, f"Expected 205 records, got {total_records}"

    print("Step 6: Wrapping envelope and saving JSON artifact...")
    envelope = build_envelope(validated_records, request_id="c2_sample_export_001")
    envelope_path = samples_dir / "trajectory_sample_envelope.json"
    with open(envelope_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)
    print(f"  Saved envelope: {envelope_path.relative_to(root)}")


if __name__ == "__main__":
    main()
