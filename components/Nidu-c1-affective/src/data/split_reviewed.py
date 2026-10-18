"""
src/data/split_reviewed.py

Validates and splits reviewed domain data into domain_train.csv and domain_val.csv.
Validation Rules (for rows with reviewed=True / TRUE / true):
- Strip UTF-8 BOM.
- Reject row if text is empty.
- Reject row if annotator is empty or in {"synthetic_generator", "ai_draft"}.
- Reject row if text equals synthetic_text (case/whitespace insensitive, or similarity > 0.9).
- Reject row if confidence is not an integer in 1..5.
- Reject row if label not in approved taxonomy or 'none'.
- NEVER outputs to test_proxy.csv.
- Strictly prints counts per rejection reason; never logs raw student text.
"""

import argparse
from difflib import SequenceMatcher
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("split_reviewed")

VALID_CLASSES = {
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "none",
}

DISALLOWED_ANNOTATORS = {
    "synthetic_generator",
    "ai_draft",
}


def is_text_identical_or_similar(s1: str, s2: str, threshold: float = 0.9) -> bool:
    """Checks case- and whitespace-insensitive identity or SequenceMatcher similarity > threshold."""
    s1_norm = " ".join(str(s1).lower().split())
    s2_norm = " ".join(str(s2).lower().split())
    if not s1_norm or not s2_norm:
        return False
    if s1_norm == s2_norm:
        return True
    return SequenceMatcher(None, s1_norm, s2_norm).ratio() > threshold


def validate_reviewed_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Validates reviewed domain rows strictly.
    Returns:
        valid_df: DataFrame containing only compliant reviewed rows.
        rejection_counts: Dictionary mapping each rejection reason to count.
    """
    rejection_counts: Dict[str, int] = {
        "unreviewed_row": 0,
        "empty_text": 0,
        "invalid_annotator": 0,
        "identical_or_similar_to_synthetic": 0,
        "invalid_confidence": 0,
        "invalid_label": 0,
    }

    if "reviewed" not in df.columns:
        raise ValueError("Missing mandatory column 'reviewed'")

    # Accept True / TRUE / true / 1
    reviewed_mask = df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1"])
    unreviewed_count = int((~reviewed_mask).sum())
    rejection_counts["unreviewed_row"] = unreviewed_count

    valid_indices = []

    for idx, row in df.iterrows():
        if not bool(reviewed_mask.loc[idx]):
            continue

        row_rejected = False

        # 1. Text empty check
        raw_text = row.get("text")
        text_str = "" if pd.isna(raw_text) else str(raw_text).strip()
        if not text_str:
            rejection_counts["empty_text"] += 1
            row_rejected = True

        # 2. Annotator check
        raw_ann = row.get("annotator")
        ann_str = "" if pd.isna(raw_ann) else str(raw_ann).strip()
        if not ann_str or ann_str.lower() in DISALLOWED_ANNOTATORS:
            rejection_counts["invalid_annotator"] += 1
            row_rejected = True

        # 3. Synthetic comparison check
        if "synthetic_text" in row:
            raw_syn = row.get("synthetic_text")
            syn_str = "" if pd.isna(raw_syn) else str(raw_syn).strip()
            if syn_str and is_text_identical_or_similar(text_str, syn_str, threshold=0.9):
                rejection_counts["identical_or_similar_to_synthetic"] += 1
                row_rejected = True

        # 4. Confidence check (must be integer 1-5)
        raw_conf = row.get("confidence")
        valid_conf = False
        try:
            if not pd.isna(raw_conf):
                conf_float = float(raw_conf)
                conf_int = int(conf_float)
                if conf_float == conf_int and conf_int in {1, 2, 3, 4, 5}:
                    valid_conf = True
        except (ValueError, TypeError):
            valid_conf = False

        if not valid_conf:
            rejection_counts["invalid_confidence"] += 1
            row_rejected = True

        # 5. Label check (must be in taxonomy or 'none')
        raw_lbl = row.get("label")
        lbl_str = "" if pd.isna(raw_lbl) else str(raw_lbl).strip()
        tokens = [t.strip() for t in lbl_str.split(",") if t.strip()]
        if not tokens or not all(t in VALID_CLASSES for t in tokens):
            rejection_counts["invalid_label"] += 1
            row_rejected = True

        if not row_rejected:
            valid_indices.append(idx)

    valid_df = df.loc[valid_indices].copy()
    valid_df["text"] = valid_df["text"].astype(str).str.strip()
    valid_df = valid_df.drop_duplicates(subset=["text"]).copy()

    if "source" not in valid_df.columns:
        valid_df["source"] = "domain"

    return valid_df, rejection_counts


def split_reviewed_data(
    df: pd.DataFrame,
    val_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Splits reviewed data into train and val sets."""
    if len(df) < 5:
        train_df = df.iloc[: max(1, len(df) - 1)].copy()
        val_df = df.iloc[max(1, len(df) - 1):].copy()
        return train_df, val_df

    train_df, val_df = train_test_split(
        df,
        test_size=val_ratio,
        random_state=seed,
        shuffle=True,
    )
    return train_df, val_df


def process_and_save_splits(
    input_csv: Path,
    output_dir: Path,
    val_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Orchestrates validation, splitting, and saving of reviewed domain data."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read with utf-8-sig to strip any UTF-8 BOM
    df_raw = pd.read_csv(input_csv, encoding="utf-8-sig")
    total_raw = len(df_raw)

    valid_df, rejection_counts = validate_reviewed_data(df_raw)
    total_valid = len(valid_df)

    if total_valid == 0:
        logger.warning("No compliant rows survived validation. No splits written.")
        return {"total_input_rows": total_raw, "reviewed_valid_rows": 0, "train_rows": 0, "val_rows": 0}, rejection_counts

    train_df, val_df = split_reviewed_data(valid_df, val_ratio=val_ratio, seed=seed)

    train_path = output_dir / "domain_train.csv"
    val_path = output_dir / "domain_val.csv"

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)

    counts = {
        "total_input_rows": total_raw,
        "reviewed_valid_rows": total_valid,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
    }

    logger.info(f"Split complete: train={len(train_df)} rows, val={len(val_df)} rows")
    return counts, rejection_counts


def main():
    parser = argparse.ArgumentParser(description="Split reviewed domain data into train and val sets")
    parser.add_argument(
        "--input",
        type=str,
        default="data/interim/domain_reviewed_DRAFT.csv",
        help="Path to reviewed domain CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/interim",
        help="Directory to save domain_train.csv and domain_val.csv",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.20,
        help="Validation split ratio",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for splitting",
    )
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[2]
    inp = component_root / args.input
    if not inp.exists():
        # Fallback to double extension if present
        alt_inp = Path(str(inp) + ".csv")
        if alt_inp.exists():
            inp = alt_inp
        else:
            logger.error(f"Input file not found: {inp}")
            return

    out_dir = component_root / args.output_dir

    counts, rejections = process_and_save_splits(inp, out_dir, val_ratio=args.val_ratio, seed=args.seed)

    print("\n" + "=" * 60)
    print("REVIEWED DATA VALIDATION REJECTION COUNTS (COUNTS ONLY)")
    print("=" * 60)
    for reason, count in rejections.items():
        print(f"  {reason:36s}: {count}")
    print("-" * 60)
    print("SUMMARY COUNTS:")
    for k, v in counts.items():
        print(f"  {k:36s}: {v}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
