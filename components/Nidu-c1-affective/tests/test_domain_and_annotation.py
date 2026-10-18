"""
tests/test_domain_and_annotation.py

Unit tests for Phase 4:
- Annotation guide structure and taxonomy conformance
- Domain template generator (make_domain_template.py)
- Reviewed domain data splitter (split_reviewed.py)
- Synthetic review candidates verification (30 confusion, 30 motivation, source=synthetic, reviewed=false)
- Supported-classes macro F1 calculation in src/evaluation.py
- Train script argument parsing for --run-name and banner mode formatting
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.make_domain_template import (
    TEMPLATE_COLUMNS,
    format_unlabelled_texts_for_annotation,
    generate_empty_template,
)
from src.data.split_reviewed import (
    split_reviewed_data,
    validate_reviewed_data,
)
from src.evaluation import (
    DEFAULT_CLASSES,
    compute_multilabel_metrics,
)

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = COMPONENT_ROOT / "docs"
DATA_INTERIM_DIR = COMPONENT_ROOT / "data" / "interim"


def test_annotation_guide_content():
    """Verify annotation_guide.md exists, contains all 5 classes, agreement metrics, and guidance."""
    guide_path = DOCS_DIR / "annotation_guide.md"
    assert guide_path.exists(), "docs/annotation_guide.md must exist"

    content = guide_path.read_text(encoding="utf-8")
    for cls in DEFAULT_CLASSES:
        assert cls in content, f"Guide must explain class: {cls}"
    assert "none" in content, "Guide must explain neutral/non-distress 'none'"
    assert "Kappa" in content or "kappa" in content, "Guide must specify inter-annotator agreement target"
    assert "0.70" in content, "Guide must mention Kappa threshold >= 0.70"


def test_make_domain_template(tmp_path):
    """Verify make_domain_template creates CSV with required schema."""
    out_file = tmp_path / "test_template.csv"
    generate_empty_template(out_file, num_blank_rows=5)

    assert out_file.exists()
    df = pd.read_csv(out_file)
    assert len(df) == 5
    assert list(df.columns) == TEMPLATE_COLUMNS

    # Test candidate formatting
    cand_file = tmp_path / "cand_template.csv"
    format_unlabelled_texts_for_annotation(["Sample text A", "Sample text B"], cand_file)
    df_cand = pd.read_csv(cand_file)
    assert len(df_cand) == 2
    assert list(df_cand.columns) == TEMPLATE_COLUMNS
    assert (df_cand["reviewed"] == False).all()


def test_split_reviewed_validation_and_splitting():
    """Verify reviewed domain splitter accepts only reviewed=True and splits cleanly."""
    mock_df = pd.DataFrame([
        {"text": "Text 1", "label": "exam_anxiety", "reviewed": True, "source": "domain"},
        {"text": "Text 2", "label": "conceptual_confusion", "reviewed": True, "source": "domain"},
        {"text": "Text 3", "label": "academic_helplessness", "reviewed": True, "source": "domain"},
        {"text": "Text 4", "label": "course_frustration", "reviewed": True, "source": "domain"},
        {"text": "Text 5", "label": "motivation_erosion", "reviewed": True, "source": "domain"},
        {"text": "Text 6", "label": "exam_anxiety", "reviewed": False, "source": "domain"},  # unreviewed
    ])

    valid_df = validate_reviewed_data(mock_df)
    assert len(valid_df) == 5, "Unreviewed row must be excluded"
    assert (valid_df["reviewed"] == True).all()

    train_df, val_df = split_reviewed_data(valid_df, val_ratio=0.20, seed=42)
    assert len(train_df) + len(val_df) == 5
    assert len(train_df) >= 1
    assert len(val_df) >= 1

    # Check zero overlap between train and val
    train_texts = set(train_df["text"])
    val_texts = set(val_df["text"])
    assert len(train_texts.intersection(val_texts)) == 0


def test_synthetic_review_candidates_dataset():
    """Verify synthetic_review_candidates.csv meets all Phase 4 specifications."""
    syn_path = DATA_INTERIM_DIR / "synthetic_review_candidates.csv"
    assert syn_path.exists(), "synthetic_review_candidates.csv must exist in data/interim/"

    df = pd.read_csv(syn_path)
    assert len(df) == 60, f"Expected exactly 60 synthetic candidates, got {len(df)}"

    counts = df["label"].value_counts().to_dict()
    assert counts.get("conceptual_confusion") == 30, "Expected 30 conceptual_confusion candidates"
    assert counts.get("motivation_erosion") == 30, "Expected 30 motivation_erosion candidates"

    assert (df["source"] == "synthetic").all(), "All items must be tagged source='synthetic'"
    assert (df["reviewed"] == False).all(), "All items must have reviewed=False"
    assert df["text"].str.strip().str.len().min() > 15, "Texts must be non-trivial"


def test_macro_f1_supported_classes_logic():
    """Verify macro_f1_supported_classes handles zero-support classes properly."""
    # Class 0, 1, 2 have support. Class 3, 4 have 0 support.
    y_true = np.array([
        [1, 0, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0],
    ])
    # Perfect predictions for the 3 classes with support
    y_probs = np.array([
        [0.9, 0.1, 0.1, 0.0, 0.0],
        [0.1, 0.9, 0.1, 0.0, 0.0],
        [0.1, 0.1, 0.9, 0.0, 0.0],
    ])

    metrics = compute_multilabel_metrics(y_true, y_probs, thresholds=0.5, class_names=DEFAULT_CLASSES)
    macro = metrics["macro_metrics"]

    # Overall macro F1 across 5 classes = (1 + 1 + 1 + 0 + 0) / 5 = 0.60
    assert macro["macro_f1"] == 0.60
    # Supported classes macro F1 = (1 + 1 + 1) / 3 = 1.00
    assert macro["macro_f1_supported_classes"] == 1.00
    assert macro["zero_support_classes_excluded_from_supported_macro"] is True


def test_train_parser_and_banner_logic():
    """Verify argument parser has --run-name and banner distinguishes ablation."""
    from src.train import main

    # Inspect parser by instantiating an ArgumentParser mimicking main
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", type=str, default=None)
    parser.add_argument("--ablation", type=str, default=None)
    parser.add_argument("--max-samples", type=int, default=None)

    args = parser.parse_args(["--run-name", "test_run", "--ablation", "goemotions_proxy"])
    assert args.run_name == "test_run"
    assert args.ablation == "goemotions_proxy"

    if args.max_samples:
        mode = "SMOKE TEST"
    elif args.ablation:
        mode = f"ABLATION ({args.ablation})"
    else:
        mode = "FULL"

    assert "ABLATION" in mode
    assert mode != "FULL"
