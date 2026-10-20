"""
src/probe_eval.py

Evaluates the trained DistilRoBERTa model on reviewed domain probe sentences.
Rules:
- Strictly evaluates only rows that pass validation in src/data/split_reviewed.py.
- If fewer than 20 valid rows exist, prints warning and skips metrics.
- Prints counts, per-class recall, and number of misses.
- Explicitly labelled: "domain probe (AI-drafted, author-verified), small N".
- NEVER uses domain_reviewed_DRAFT.csv as training data.
- NEVER logs or prints raw student text or component keys.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Optional

# Ensure component root is in sys.path
_comp_root = Path(__file__).resolve().parents[1]
if str(_comp_root) not in sys.path:
    sys.path.insert(0, str(_comp_root))

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.data.split_reviewed import validate_reviewed_data
from src.evaluation import DEFAULT_CLASSES
from src.train import TextDataset, predict_probabilities

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe_eval")


def run_probe_evaluation(
    probe_csv_path: Path,
    component_root: Path,
    device_name: str = "cpu",
    batch_size: int = 32,
) -> Optional[Dict[str, any]]:
    """Evaluates compliant reviewed probe rows and prints per-class recall and misses."""
    if not probe_csv_path.exists():
        alt_path = Path(str(probe_csv_path) + ".csv")
        if alt_path.exists():
            probe_csv_path = alt_path
        else:
            logger.error(f"Probe file not found: {probe_csv_path}")
            return None

    # 1. Load and validate
    df_raw = pd.read_csv(probe_csv_path, encoding="utf-8-sig")
    valid_df, rejections = validate_reviewed_data(df_raw)

    print("\n" + "=" * 65)
    print("PROBE VALIDATION REJECTION COUNTS (COUNTS ONLY)")
    print("=" * 65)
    for reason, cnt in rejections.items():
        print(f"  {reason:36s}: {cnt}")
    print("-" * 65)
    print(f"  Total input rows                   : {len(df_raw)}")
    print(f"  Total valid compliant rows         : {len(valid_df)}")
    print("=" * 65)

    # 2. Check minimum sample threshold
    if len(valid_df) < 20:
        print(f"\n[WARNING] Fewer than 20 valid rows exist ({len(valid_df)} rows). Skipping metrics.\n")
        return None

    # 3. Load checkpoint and thresholds
    checkpoint_dir = component_root / "models" / "checkpoint-best"
    thresh_file = component_root / "models" / "thresholds.json"

    if not checkpoint_dir.exists():
        logger.error(f"Checkpoint directory missing: {checkpoint_dir}")
        return None
    if not thresh_file.exists():
        logger.error(f"Thresholds file missing: {thresh_file}")
        return None

    with open(thresh_file, "r", encoding="utf-8") as f:
        thresholds = json.load(f)

    device = torch.device(device_name)
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir)).to(device)

    # 4. Construct ground truth binary vectors
    y_true = np.zeros((len(valid_df), len(DEFAULT_CLASSES)), dtype=int)
    for i, (_, row) in enumerate(valid_df.iterrows()):
        lbl_str = str(row["label"])
        tokens = [t.strip() for t in lbl_str.split(",") if t.strip()]
        for c_idx, cls in enumerate(DEFAULT_CLASSES):
            if cls in tokens:
                y_true[i, c_idx] = 1

    # 5. Predict probabilities
    dataset = TextDataset(
        valid_df["text"].tolist(),
        labels=y_true.astype(float),
        tokenizer=tokenizer,
        max_length=64,
    )
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    probs = predict_probabilities(model, dataloader, device)

    # 6. Apply thresholds and compute hits/misses
    y_pred = np.zeros_like(y_true, dtype=int)
    for c_idx, cls in enumerate(DEFAULT_CLASSES):
        t = thresholds.get(cls, 0.50)
        y_pred[:, c_idx] = (probs[:, c_idx] >= t).astype(int)

    results_per_class: Dict[str, Dict[str, any]] = {}
    total_misses = 0

    print("\n" + "=" * 65)
    print("EVALUATION: domain probe (AI-drafted, author-verified), small N")
    print("=" * 65)
    print(f"Total Probe Evaluated Samples: {len(valid_df)}")
    print(f"Applied Thresholds: {thresholds}")
    print("-" * 65)
    print(f"{'Class Name':24s} | {'Support':7s} | {'Hits':5s} | {'Misses':6s} | {'Recall':7s} | {'False Alarms':12s}")
    print("-" * 65)

    for c_idx, cls in enumerate(DEFAULT_CLASSES):
        yt = y_true[:, c_idx]
        yp = y_pred[:, c_idx]

        support = int(yt.sum())
        hits = int(((yt == 1) & (yp == 1)).sum())
        misses = int(((yt == 1) & (yp == 0)).sum())
        false_alarms = int(((yt == 0) & (yp == 1)).sum())
        recall = round(hits / max(1, support), 4) if support > 0 else 0.0

        total_misses += misses
        results_per_class[cls] = {
            "support": support,
            "hits": hits,
            "misses": misses,
            "false_alarms": false_alarms,
            "recall": recall,
            "applied_threshold": thresholds.get(cls, 0.50),
        }

        print(f"{cls:24s} | {support:7d} | {hits:5d} | {misses:6d} | {recall:7.4f} | {false_alarms:12d}")

    print("-" * 65)
    print(f"Total Across Classes: Misses = {total_misses}")
    print("=" * 65 + "\n")

    return {
        "evaluation_label": "domain probe (AI-drafted, author-verified), small N",
        "sample_count": len(valid_df),
        "results_per_class": results_per_class,
        "total_misses": total_misses,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate model on reviewed domain probe dataset")
    parser.add_argument(
        "--input",
        type=str,
        default="data/interim/domain_reviewed_DRAFT.csv",
        help="Path to reviewed domain probe CSV",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Inference batch size",
    )
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[1]
    probe_path = component_root / args.input

    run_probe_evaluation(probe_path, component_root, device_name="cpu", batch_size=args.batch_size)


if __name__ == "__main__":
    main()
