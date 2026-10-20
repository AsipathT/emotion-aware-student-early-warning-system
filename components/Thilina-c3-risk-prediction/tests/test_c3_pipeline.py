"""
components/Thilina-c3-risk-prediction/tests/test_c3_pipeline.py

Unit and Contract Tests for Component 3 (Multimodal Risk Prediction).
"""

import pytest
import numpy as np
import pandas as pd
from src.generate_multimodal_dataset import generate_multimodal_data
from src.model import map_risk_tier, ALL_FEATURE_COLS
from src.ingest_client import C3IngestClient


def test_multimodal_dataset_generation():
    train_df, truth_df = generate_multimodal_data(num_students=10, num_weeks=4, seed=123)
    assert len(train_df) <= 40
    assert len(truth_df) == 10
    assert "pid" in train_df.columns
    assert "cohort" in train_df.columns
    assert "withdraws_within_k_weeks" in train_df.columns

    # Verify former leakage columns are absent from training table
    assert "actual_composite_risk" not in train_df.columns
    assert "risk_tier" not in train_df.columns
    assert "actual_dropout" not in train_df.columns

    # Verify all expected feature columns are present
    for col in ALL_FEATURE_COLS:
        assert col in train_df.columns, f"Missing feature: {col}"

    # Verify value ranges
    assert (train_df["quiz_score"] >= 0.0).all() and (train_df["quiz_score"] <= 100.0).all()
    valid_affect = train_df["exam_anxiety"].dropna()
    assert (valid_affect >= 0.0).all() and (valid_affect <= 1.0).all()
    assert set(train_df["withdraws_within_k_weeks"].unique()).issubset({0, 1})


def test_map_risk_tier():
    assert map_risk_tier(0.15) == "low"
    assert map_risk_tier(0.45) == "medium"
    assert map_risk_tier(0.72) == "high"
    assert map_risk_tier(0.92) == "critical"


def test_ingest_client_envelope():
    client = C3IngestClient(platform_url="http://localhost:8000", component_key="test_key")
    sample_data = [
        {
            "pid": "STU_12345678",
            "course_id": "CS101",
            "week_index": 3,
            "risk_score": 0.75,
            "risk_tier": "high",
            "modality_contributions": {
                "affective": 0.40,
                "behavioral": 0.35,
                "academic": 0.25,
            },
            "top_drivers": ["High Conceptual Confusion", "Low LMS Activity"],
        }
    ]

    envelope = client.build_envelope(sample_data)
    assert envelope["schema_version"] == "1.0"
    assert envelope["source"] == "c3"
    assert "request_id" in envelope
    assert "generated_at" in envelope
    assert len(envelope["data"]) == 1
    assert envelope["data"][0]["risk_tier"] == "high"
