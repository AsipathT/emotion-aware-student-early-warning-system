"""
Configuration and constants for Component 2 (Behavioral Engagement Trajectory).
"""

import os
from pathlib import Path
from typing import List

# ── Core Constants ────────────────────────────────────────────────────────────
WEEK_DAYS: int = 7
KEYS: List[str] = ["code_module", "code_presentation", "id_student"]
WINDOW_HALF: int = 3
FEATURE_LOOKBACK: int = 5
MIN_T: int = 3
S_TREND: float = 0.20
RESID_SD_HI: float = 1.0
S_FLAT: float = 0.10
DORMANT_POLICY: str = "declining_flag"  # Allowed: "exclude_and_flag", "stable_flag", "declining_flag"
DORMANT_ZERO_WEEKS: int = 7
DORMANT_RULE_CONFIDENCE: float = 0.86
INDICATOR_DIFF: float = 0.5
LATE_DELAY_HOURS: float = 24.0
INFER_MIN_WEEKS: int = MIN_T + 1

REQUIRED_OULAD_FILES: List[str] = [
    "assessments.csv",
    "courses.csv",
    "studentAssessment.csv",
    "studentInfo.csv",
    "studentRegistration.csv",
    "studentVle.csv",
    "vle.csv",
]


def component_root() -> Path:
    """Returns the root path of components/c2-behavioral."""
    return Path(__file__).resolve().parent.parent


def get_oulad_dir() -> Path:
    """
    Resolves and validates the directory containing the 7 OULAD CSV files.
    Reads path from the OULAD_DIR environment variable.
    """
    raw_dir = os.environ.get("OULAD_DIR")
    if not raw_dir or not raw_dir.strip():
        raise RuntimeError(
            "Environment variable OULAD_DIR is missing or empty. "
            "Please set it to your OULAD dataset folder (in PowerShell: $env:OULAD_DIR=\"<path>\")."
        )

    oulad_path = Path(raw_dir.strip()).resolve()
    if not oulad_path.exists() or not oulad_path.is_dir():
        raise RuntimeError(
            f"OULAD directory does not exist or is not a directory: {oulad_path}. "
            "Please check your $env:OULAD_DIR setting."
        )

    missing = [fname for fname in REQUIRED_OULAD_FILES if not (oulad_path / fname).is_file()]
    if missing:
        raise RuntimeError(
            f"OULAD directory '{oulad_path}' is missing required CSV file(s): {', '.join(sorted(missing))}."
        )

    return oulad_path


def day_to_week(day: int) -> int:
    """Converts day offset to zero-indexed week using integer floor division."""
    return int(day) // 7


# ── Low-Activity Indicator Constants (a priori design constants, not tuned) ──
LOW_ACTIVITY_RATIO: float = 0.25
LOW_ACTIVITY_MIN_WEEKS: int = 6

