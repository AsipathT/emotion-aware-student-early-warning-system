#!/usr/bin/env python3
"""
scripts/export_contract_schemas.py

Feature 24: JSON Schema Exporter for Data Contracts.
Exports machine-readable JSON Schema files for every v1 model plus the Envelope
to contracts/v1/<ModelName>.json with sorted keys, deterministic formatting,
and a trailing newline.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add backend directory to sys.path so imports resolve seamlessly
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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

MODELS_TO_EXPORT = [
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


def generate_schema(model: Any) -> Dict[str, Any]:
    """Generates the JSON Schema dictionary for a given model or generic."""
    return model.model_json_schema()


def export_schemas(output_dir: Path) -> None:
    """Exports all JSON Schema files to output_dir with sorted keys and newline."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Exporting contract schemas to: {output_dir}")

    for model_name, model_cls in MODELS_TO_EXPORT:
        schema = generate_schema(model_cls)
        # Ensure title matches model name cleanly
        schema["title"] = model_name

        file_path = output_dir / f"{model_name}.json"
        content = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [OK] Exported {model_name}.json ({len(content)} bytes)")

    print(f"Successfully exported {len(MODELS_TO_EXPORT)} contract schemas.")


if __name__ == "__main__":
    target_dir = project_root / "contracts" / "v1"
    export_schemas(target_dir)
