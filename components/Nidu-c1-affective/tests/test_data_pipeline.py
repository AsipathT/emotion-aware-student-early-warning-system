"""
tests/test_data_pipeline.py

Unit tests for Phase 2 data pipeline:
- Text normalization (tweet artefacts, mentions, URLs, hashtags)
- Ignore-label logic and filtering
- Zero cross-split text leakage
- Binary multi-label output shape and values
- Positive class weights calculation and clipping
"""

from pathlib import Path
import json
import pandas as pd
import pytest

from src.data.prepare import normalize_text, compute_pos_weights

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = COMPONENT_ROOT / "data" / "processed"
METRICS_DIR = COMPONENT_ROOT / "reports" / "metrics"
TARGET_CLASSES = [
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
]


def test_normalize_text_tweet_artefacts():
    """Verify that normalize_text cleans mentions, URLs, and hashtags properly."""
    raw = "Hey @prof_smith check https://lms.uni.edu/exam and www.canvas.com #midterm_exam! Also /u/reddit_user"
    clean = normalize_text(raw)
    assert "@prof_smith" not in clean
    assert "[USER]" in clean
    assert "https://" not in clean
    assert "[URL]" in clean
    assert "#midterm_exam" not in clean
    assert "midterm_exam" in clean
    assert "/u/reddit_user" not in clean


def test_processed_files_exist():
    """Verify train.csv, val.csv, and test_proxy.csv exist."""
    for split_name in ["train.csv", "val.csv", "test_proxy.csv"]:
        fpath = PROCESSED_DIR / split_name
        assert fpath.exists(), f"Processed split {split_name} missing from {PROCESSED_DIR}"
        assert fpath.stat().st_size > 0, f"Processed split {split_name} is empty"


@pytest.fixture(scope="module")
def processed_dfs():
    train = pd.read_csv(PROCESSED_DIR / "train.csv")
    val = pd.read_csv(PROCESSED_DIR / "val.csv")
    test_proxy = pd.read_csv(PROCESSED_DIR / "test_proxy.csv")
    return {"train": train, "val": val, "test_proxy": test_proxy}


def test_label_shapes_and_columns(processed_dfs):
    """Verify all 5 target classes and required metadata columns exist in each split."""
    expected_cols = {"text", "source"} | set(TARGET_CLASSES)
    for name, df in processed_dfs.items():
        assert expected_cols.issubset(set(df.columns)), f"Columns missing in {name} split"
        # Check that target columns are strictly binary (0 or 1)
        for cls in TARGET_CLASSES:
            unique_vals = set(df[cls].unique())
            assert unique_vals.issubset({0, 1}), f"Non-binary values in {name}[{cls}]: {unique_vals}"


def test_source_column_proxy_values(processed_dfs):
    """Verify source column contains valid proxy tags only."""
    valid_sources = {"goemotions_proxy", "emotion4_proxy"}
    for name, df in processed_dfs.items():
        sources = set(df["source"].unique())
        assert sources.issubset(valid_sources), f"Invalid sources found in {name}: {sources}"


def test_zero_cross_split_leakage(processed_dfs):
    """Ensure no text appears in two splits (train, val, test_proxy are completely disjoint)."""
    train_texts = set(processed_dfs["train"]["text"].dropna())
    val_texts = set(processed_dfs["val"]["text"].dropna())
    test_texts = set(processed_dfs["test_proxy"]["text"].dropna())

    train_val_leakage = train_texts & val_texts
    train_test_leakage = train_texts & test_texts
    val_test_leakage = val_texts & test_texts

    assert len(train_val_leakage) == 0, f"Found {len(train_val_leakage)} leaked texts between train and val"
    assert len(train_test_leakage) == 0, f"Found {len(train_test_leakage)} leaked texts between train and test"
    assert len(val_test_leakage) == 0, f"Found {len(val_test_leakage)} leaked texts between val and test"


def test_pos_weights_calculation_and_clipping(processed_dfs):
    """Verify positive class weights calculation and clipping at 10.0."""
    train_df = processed_dfs["train"]
    weights = compute_pos_weights(train_df, TARGET_CLASSES, clip_max=10.0)

    for cls in TARGET_CLASSES:
        assert cls in weights
        assert weights[cls] >= 1.0, f"Weight for {cls} should be >= 1.0 given class imbalance"
        assert weights[cls] <= 10.0, f"Weight for {cls} exceeded clip max of 10.0: {weights[cls]}"

    # Verify matching saved class_weights.json
    weights_json_path = METRICS_DIR / "class_weights.json"
    assert weights_json_path.exists()
    with open(weights_json_path, "r", encoding="utf-8") as f:
        saved_weights = json.load(f)["pos_weights"]
    assert saved_weights == weights
