"""
src/data/split_reviewed.py

Validates and splits reviewed domain data into domain_train.csv and domain_val.csv.
Rules:
- Only rows marked reviewed=True are processed.
- Labels must belong to the approved 5-class taxonomy or 'none'.
- NEVER outputs to test_proxy.csv (domain data is strictly for training/validation adaptation).
- Stratified or seeded deterministic split (default 80% train, 20% val).
- Strictly prints counts and distributions; never logs raw student text.
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple
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


def validate_reviewed_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validates schema, review status, and labels for domain data."""
    required_cols = ["text", "label", "reviewed"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing mandatory column: '{col}'")

    # Filter strictly for reviewed items
    reviewed_mask = df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    valid_df = df[reviewed_mask].copy()
    if len(valid_df) == 0:
        raise ValueError("No rows found with reviewed=True")

    # Drop missing or empty texts
    valid_df["text"] = valid_df["text"].fillna("").astype(str).str.strip()
    valid_df = valid_df[valid_df["text"].str.len() > 0].copy()

    # Drop duplicates
    valid_df = valid_df.drop_duplicates(subset=["text"]).copy()

    # Validate labels
    def check_labels(lbl_str: str) -> bool:
        tokens = [t.strip() for t in str(lbl_str).split(",") if t.strip()]
        if not tokens:
            return False
        return all(t in VALID_CLASSES for t in tokens)

    valid_mask = valid_df["label"].apply(check_labels)
    valid_df = valid_df[valid_mask].copy()

    # Ensure source column exists and defaults to domain
    if "source" not in valid_df.columns:
        valid_df["source"] = "domain"

    return valid_df


def split_reviewed_data(
    df: pd.DataFrame,
    val_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Splits reviewed data into train and val sets."""
    if len(df) < 5:
        # For tiny sample sizes, place at least 1 in val if possible
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
) -> Dict[str, int]:
    """Orchestrates validation, splitting, and saving of reviewed domain data."""
    output_dir.mkdir(parents=True, exist_ok=True)

    df_raw = pd.read_csv(input_csv)
    total_raw = len(df_raw)
    valid_df = validate_reviewed_data(df_raw)
    total_valid = len(valid_df)

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
    logger.info(f"Domain train saved to: {train_path}")
    logger.info(f"Domain val saved to: {val_path}")
    return counts


def main():
    parser = argparse.ArgumentParser(description="Split reviewed domain data into train and val sets")
    parser.add_argument(
        "--input",
        type=str,
        default="data/interim/reviewed_domain.csv",
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
    out_dir = component_root / args.output_dir

    if not inp.exists():
        logger.error(f"Input file not found: {inp}")
        return

    counts = process_and_save_splits(inp, out_dir, val_ratio=args.val_ratio, seed=args.seed)
    print("\n" + "=" * 50)
    print("REVIEWED DOMAIN DATA SPLIT SUMMARY (COUNTS ONLY)")
    print("=" * 50)
    for k, v in counts.items():
        print(f"  {k:24s}: {v}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
