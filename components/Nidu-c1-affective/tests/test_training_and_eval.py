"""
tests/test_training_and_eval.py

Unit tests for Phase 3 (training, evaluation, baselines, and probe template):
- Multi-label metric calculations (macro F1, ROC-AUC, precision, recall)
- Threshold tuning logic on validation data
- Probe sentences template verification (30 rows, 5 classes)
- Metric report artifacts validity and 'proxy test' labelling
- Colab notebook structure and upload/download directives
- Model output shape verification
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.evaluation import (
    DEFAULT_CLASSES,
    compute_multilabel_metrics,
    tune_thresholds_on_val,
)

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = COMPONENT_ROOT / "reports" / "metrics"
NOTEBOOKS_DIR = COMPONENT_ROOT / "notebooks"
DATA_INTERIM_DIR = COMPONENT_ROOT / "data" / "interim"


def test_tune_thresholds_on_val_logic():
    """Verify threshold tuning finds valid optimal thresholds in range [0.10, 0.90]."""
    y_true = np.array([
        [1, 0, 0, 1, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 1, 0, 0],
        [0, 0, 0, 1, 1],
    ])
    y_probs = np.array([
        [0.85, 0.10, 0.20, 0.75, 0.05],
        [0.15, 0.90, 0.05, 0.30, 0.10],
        [0.70, 0.20, 0.80, 0.10, 0.05],
        [0.20, 0.10, 0.15, 0.80, 0.90],
    ])

    thresholds = tune_thresholds_on_val(y_true, y_probs, class_names=DEFAULT_CLASSES)
    assert len(thresholds) == 5
    for cls in DEFAULT_CLASSES:
        assert 0.10 <= thresholds[cls] <= 0.90


def test_compute_multilabel_metrics():
    """Verify metric computation returns valid macro and per-class metrics."""
    y_true = np.array([[1, 0, 0, 1, 0], [0, 1, 1, 0, 0]])
    y_probs = np.array([[0.8, 0.2, 0.1, 0.9, 0.0], [0.1, 0.7, 0.6, 0.2, 0.1]])

    metrics = compute_multilabel_metrics(y_true, y_probs, thresholds=0.5, class_names=DEFAULT_CLASSES)
    macro = metrics["macro_metrics"]
    assert 0.0 <= macro["macro_f1"] <= 1.0
    assert 0.0 <= macro["macro_precision"] <= 1.0
    assert 0.0 <= macro["macro_recall"] <= 1.0
    assert len(metrics["per_class_metrics"]) == 5


def test_probe_sentences_template_integrity():
    """Verify probe_sentences.csv exists, has 30 sentences, correct columns, and 6 per class."""
    probe_path = DATA_INTERIM_DIR / "probe_sentences.csv"
    assert probe_path.exists(), "probe_sentences.csv must exist in data/interim/"

    df = pd.read_csv(probe_path)
    assert len(df) == 30, f"Expected exactly 30 probe sentences, got {len(df)}"
    assert list(df.columns) == ["text", "expected_class", "notes"]
    assert df["text"].str.strip().str.len().min() > 10, "Probe sentences must be non-empty"

    class_counts = df["expected_class"].value_counts().to_dict()
    assert set(class_counts.keys()) == set(DEFAULT_CLASSES), "Classes must match DEFAULT_CLASSES"
    for cls in DEFAULT_CLASSES:
        assert class_counts[cls] == 6, f"Expected 6 sentences for {cls}, got {class_counts[cls]}"


def test_baseline_metric_reports_exist_and_labelled():
    """Verify all expected metric reports exist and are explicitly labelled 'proxy test'."""
    expected_reports = [
        "baseline_tfidf.json",
        "baseline_vader.json",
        "ablation_tfidf_goemotions.json",
        "distilroberta_smoke.json",
    ]
    for rep in expected_reports:
        p = METRICS_DIR / rep
        assert p.exists(), f"Metric report {rep} is missing"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("evaluation_type") == "proxy test", f"{rep} must be labelled 'proxy test'"


def test_colab_notebook_structure():
    """Verify colab_train.ipynb exists, has cells, and contains essential setup instructions."""
    nb_path = NOTEBOOKS_DIR / "colab_train.ipynb"
    assert nb_path.exists(), "colab_train.ipynb must exist in notebooks/"
    with open(nb_path, "r", encoding="utf-8") as f:
        nb_data = json.load(f)
    assert "cells" in nb_data
    content = json.dumps(nb_data)
    assert "google.colab" in content
    assert "requirements-lock" in content  # instruction warns not to install torch from lock


def test_model_forward_pass_shape():
    """Verify DistilRoBERTa model outputs 5 logits for multi-label classification."""
    tokenizer = AutoTokenizer.from_pretrained("distilroberta-base")
    model = AutoModelForSequenceClassification.from_pretrained(
        "distilroberta-base", num_labels=5, problem_type="multi_label_classification"
    )
    tokens = tokenizer(["I am worried about my exam."], return_tensors="pt")
    with torch.no_grad():
        out = model(**tokens)
    assert out.logits.shape == (1, 5)
