"""
backend/tests/test_contract_schema_sync.py

Feature 24 CI Verification Test:
Regenerates JSON Schemas in-memory for all contract models and Envelope,
comparing each against the committed files under contracts/v1/<ModelName>.json.
Fails with a helpful message if files differ or are missing.
"""

import json
from pathlib import Path
import pytest

from app.schemas.contract.common import Envelope
from app.schemas.contract.v1 import (
    AcademicRecord,
    AffectiveWeeklyVector,
    BehaviorWeeklyRecord,
    EngagementTrajectory,
    InterventionOutcome,
    InterventionRecommendation,
    RiskAssessment,
    TextMessageRecord,
)

MODELS = [
    ("Envelope", Envelope),
    ("TextMessageRecord", TextMessageRecord),
    ("BehaviorWeeklyRecord", BehaviorWeeklyRecord),
    ("AcademicRecord", AcademicRecord),
    ("AffectiveWeeklyVector", AffectiveWeeklyVector),
    ("EngagementTrajectory", EngagementTrajectory),
    ("RiskAssessment", RiskAssessment),
    ("InterventionRecommendation", InterventionRecommendation),
    ("InterventionOutcome", InterventionOutcome),
]


def test_contract_schemas_are_in_sync():
    """
    Asserts that committed contracts/v1/*.json files exactly match in-memory generated
    JSON schemas. If this test fails, run:
        python scripts/export_contract_schemas.py
    """
    current_file = Path(__file__).resolve()
    repo_root = current_file.parents[2]
    candidate_paths = [
        repo_root / "contracts" / "v1",
        Path("/contracts/v1"),
        Path("/workspace/contracts/v1"),
        Path("/app/contracts/v1"),
        Path("/app/../contracts/v1").resolve(),
    ]
    contracts_dir = next((p for p in candidate_paths if p.exists()), None)

    assert contracts_dir is not None, (
        f"Contracts directory not found in candidate paths: {[str(p) for p in candidate_paths]}. "
        "Please run 'python scripts/export_contract_schemas.py'."
    )

    for model_name, model_cls in MODELS:
        file_path = contracts_dir / f"{model_name}.json"
        assert file_path.exists(), (
            f"Missing committed contract schema file: {file_path}. "
            "Please run 'python scripts/export_contract_schemas.py' to generate it."
        )

        with open(file_path, "r", encoding="utf-8") as f:
            committed_content = f.read()

        expected_schema = model_cls.model_json_schema()
        expected_schema["title"] = model_name
        expected_content = json.dumps(expected_schema, indent=2, sort_keys=True) + "\n"

        assert committed_content == expected_content, (
            f"Contract schema for '{model_name}' has drifted from the model definition!\n"
            f"The committed file '{file_path}' does not match model_json_schema().\n"
            "To fix this, execute:\n"
            "    python scripts/export_contract_schemas.py"
        )
