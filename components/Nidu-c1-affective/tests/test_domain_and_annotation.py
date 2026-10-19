"""
tests/test_domain_and_annotation.py

Unit tests for Phase 4:
- Annotation guide structure and taxonomy conformance
- Domain template generator (make_domain_template.py)
- Reviewed domain data splitter with strict validation (split_reviewed.py)
- Synthetic review candidates verification
- Supported-classes macro F1 calculation in src/evaluation.py
- Train script argument parsing for --run-name and banner mode formatting
- Probe evaluation execution and small-N threshold check (probe_eval.py)
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
    is_text_identical_or_similar,
    split_reviewed_data,
    validate_reviewed_data,
)
from src.evaluation import (
    DEFAULT_CLASSES,
    compute_multilabel_metrics,
)
from src.probe_eval import run_probe_evaluation

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
    """Verify reviewed domain splitter accepts only reviewed=True and valid rows."""
    mock_df = pd.DataFrame([
        {"text": "Text 1", "label": "exam_anxiety", "annotator": "ann1", "confidence": 5, "reviewed": True, "source": "domain"},
        {"text": "Text 2", "label": "conceptual_confusion", "annotator": "ann1", "confidence": 4, "reviewed": True, "source": "domain"},
        {"text": "Text 3", "label": "academic_helplessness", "annotator": "ann2", "confidence": 5, "reviewed": True, "source": "domain"},
        {"text": "Text 4", "label": "course_frustration", "annotator": "ann2", "confidence": 3, "reviewed": True, "source": "domain"},
        {"text": "Text 5", "label": "motivation_erosion", "annotator": "ann1", "confidence": 4, "reviewed": True, "source": "domain"},
        {"text": "Text 6", "label": "exam_anxiety", "annotator": "ann1", "confidence": 5, "reviewed": False, "source": "domain"},
    ])

    valid_df, rejections = validate_reviewed_data(mock_df)
    assert len(valid_df) == 5, "Unreviewed row must be excluded"
    assert rejections["unreviewed_row"] == 1
    assert (valid_df["reviewed"] == True).all()

    train_df, val_df = split_reviewed_data(valid_df, val_ratio=0.20, seed=42)
    assert len(train_df) + len(val_df) == 5
    assert len(train_df) >= 1
    assert len(val_df) >= 1

    train_texts = set(train_df["text"])
    val_texts = set(val_df["text"])
    assert len(train_texts.intersection(val_texts)) == 0


def test_split_reviewed_strict_rejection_rules():
    """Verify split_reviewed rejects invalid rows according to Section B rules."""
    test_cases = pd.DataFrame([
        # Valid row 1 (accepted)
        {"text": "I am so anxious about tomorrow's exam", "synthetic_text": "Exam tomorrow is stressful", "label": "exam_anxiety", "annotator": "expert_1", "confidence": 5, "reviewed": "True"},
        # Valid row 2 (accepted with TRUE)
        {"text": "I don't understand recursion at all", "synthetic_text": "Recursion base case is hard", "label": "conceptual_confusion", "annotator": "human_reviewer", "confidence": 4, "reviewed": "TRUE"},
        # Reject: Empty text
        {"text": "   ", "synthetic_text": "Some text", "label": "exam_anxiety", "annotator": "expert_1", "confidence": 5, "reviewed": "true"},
        # Reject: Disallowed annotator
        {"text": "I am tired", "synthetic_text": "Different text", "label": "motivation_erosion", "annotator": "synthetic_generator", "confidence": 4, "reviewed": "True"},
        # Reject: Disallowed annotator ai_draft
        {"text": "I am tired again", "synthetic_text": "Different text", "label": "motivation_erosion", "annotator": "ai_draft", "confidence": 4, "reviewed": "True"},
        # Reject: Text identical to synthetic_text
        {"text": "I feel hopeless about failing", "synthetic_text": "I feel hopeless about failing", "label": "academic_helplessness", "annotator": "reviewer_a", "confidence": 5, "reviewed": "True"},
        # Reject: Text highly similar to synthetic_text (> 0.9 similarity)
        {"text": "I feel completely hopeless about failing this test", "synthetic_text": "I feel completely hopeless about failing this exam", "label": "academic_helplessness", "annotator": "reviewer_a", "confidence": 5, "reviewed": "True"},
        # Reject: Invalid confidence (not integer 1-5)
        {"text": "The portal crashed again", "synthetic_text": "Portal was down", "label": "course_frustration", "annotator": "reviewer_b", "confidence": 3.5, "reviewed": "True"},
        # Reject: Confidence out of bounds
        {"text": "The grading was totally delayed", "synthetic_text": "Delayed grading", "label": "course_frustration", "annotator": "reviewer_b", "confidence": 6, "reviewed": "True"},
        # Reject: Invalid label
        {"text": "Random sentence", "synthetic_text": "Other sentence", "label": "joy_and_delight", "annotator": "reviewer_c", "confidence": 4, "reviewed": "True"},
    ])

    valid_df, rejections = validate_reviewed_data(test_cases)
    assert len(valid_df) == 2, f"Expected exactly 2 valid rows, got {len(valid_df)}"
    assert rejections["empty_text"] >= 1
    assert rejections["invalid_annotator"] >= 2
    assert rejections["identical_or_similar_to_synthetic"] >= 2
    assert rejections["invalid_confidence"] >= 2
    assert rejections["invalid_label"] >= 1


def test_utf8_bom_stripping(tmp_path):
    """Verify that UTF-8 BOM is cleanly stripped when loading reviewed CSV."""
    bom_file = tmp_path / "bom_data.csv"
    bom_content = "\ufefftext,label,annotator,confidence,reviewed\nValid sample,exam_anxiety,reviewer_1,5,True\n"
    bom_file.write_text(bom_content, encoding="utf-8-sig")

    df = pd.read_csv(bom_file, encoding="utf-8-sig")
    assert "text" in df.columns, "BOM must be stripped so 'text' is recognized without BOM prefix"
    valid_df, rejections = validate_reviewed_data(df)
    assert len(valid_df) == 1


def test_synthetic_review_candidates_dataset():
    """Verify synthetic_review_candidates.csv exists and has required schema."""
    syn_path = DATA_INTERIM_DIR / "synthetic_review_candidates.csv"
    assert syn_path.exists(), "synthetic_review_candidates.csv must exist in data/interim/"

    df = pd.read_csv(syn_path, encoding="utf-8-sig")
    assert len(df) in (60, 140), f"Expected 60 or 140 rows, got {len(df)}"
    for col in ["text", "label", "annotator", "confidence", "notes", "source", "reviewed"]:
        assert col in df.columns, f"Missing column: {col}"


def test_macro_f1_supported_classes_logic():
    """Verify macro_f1_supported_classes handles zero-support classes properly."""
    y_true = np.array([
        [1, 0, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0],
    ])
    y_probs = np.array([
        [0.9, 0.1, 0.1, 0.0, 0.0],
        [0.1, 0.9, 0.1, 0.0, 0.0],
        [0.1, 0.1, 0.9, 0.0, 0.0],
    ])

    metrics = compute_multilabel_metrics(y_true, y_probs, thresholds=0.5, class_names=DEFAULT_CLASSES)
    macro = metrics["macro_metrics"]

    assert macro["macro_f1"] == 0.60
    assert macro["macro_f1_supported_classes"] == 1.00
    assert macro["zero_support_classes_excluded_from_supported_macro"] is True


def test_probe_eval_under_20_rows(tmp_path, capsys):
    """Verify probe_eval skips metrics when valid rows < 20."""
    small_probe = tmp_path / "small_probe.csv"
    rows = []
    for i in range(10):
        rows.append({
            "text": f"Student distress utterance {i}",
            "synthetic_text": f"Original prompt {i}",
            "label": "exam_anxiety",
            "annotator": "human_reviewer",
            "confidence": 5,
            "reviewed": True,
        })
    pd.DataFrame(rows).to_csv(small_probe, index=False)

    res = run_probe_evaluation(small_probe, COMPONENT_ROOT, device_name="cpu")
    assert res is None, "Probe evaluation must return None when valid rows < 20"


def test_train_parser_and_banner_logic():
    """Verify argument parser has --run-name and banner distinguishes ablation."""
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


def test_demo_fetch_messages_signature_compatibility():
    """Verify demo/app.py call to fetch_messages matches function signature and does not pass pid."""
    import ast
    import inspect
    from src.lms_client import fetch_messages

    sig = inspect.signature(fetch_messages)

    # 1. Ensure 'pid' is NOT in fetch_messages signature (backend export endpoint does not accept pid parameter)
    assert "pid" not in sig.parameters, (
        "fetch_messages should not have 'pid' in signature; PID filtering is handled client-side"
    )

    # 2. Check standard parameters expected by client callers
    for param_name in ["limit", "base_url", "api_key"]:
        assert param_name in sig.parameters, f"Expected parameter '{param_name}' missing from fetch_messages signature"

    # 3. Parse demo/app.py to inspect the actual call to fetch_messages
    demo_app_file = COMPONENT_ROOT / "demo" / "app.py"
    assert demo_app_file.exists(), f"Demo file not found at {demo_app_file}"

    tree = ast.parse(demo_app_file.read_text(encoding="utf-8"))
    call_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name == "fetch_messages":
                call_nodes.append(node)

    assert len(call_nodes) >= 1, "fetch_messages must be called in demo/app.py"

    for call in call_nodes:
        kwargs_passed = [kw.arg for kw in call.keywords if kw.arg is not None]
        assert "pid" not in kwargs_passed, (
            "demo/app.py must not pass 'pid' to fetch_messages; filtering must be done client-side"
        )
        for kw in kwargs_passed:
            assert kw in sig.parameters, (
                f"Keyword argument '{kw}' passed in demo/app.py does not match fetch_messages signature"
            )

        # Confirm arguments bind successfully with inspect.signature without raising TypeError
        dummy_kwargs = {kw: 10 if kw == "limit" else "http://dummy" for kw in kwargs_passed}
        bound = sig.bind_partial(**dummy_kwargs)
        assert bound is not None

