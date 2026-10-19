"""
scripts/make_classify_sample.py

Generates a standalone request payload for POST /classify:
  {"records": [BehaviorRecord...], "week": 9}
Contains 12 synthetic students across weeks 0..9 (120 records total) with fixed,
hand-written click patterns demonstrating all target behavioral trajectories.
"""

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure components/c2-behavioral root is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

from service.schemas import BehaviorRecord


def make_pid(idx: int) -> str:
    """Generates a deterministic Feature 5 compliant PID from index."""
    digest = hashlib.sha256(f"demo_{idx}".encode("utf-8")).hexdigest()[:8]
    return f"STU_{digest}"


# Fixed hand-written click patterns across weeks 0..9 (10 weeks):
# 3 steadily declining, 3 steadily rising, 3 flat, 2 alternating high/low, 1 all-zero (dormant)
PATTERNS: List[List[int]] = [
    # 3 Declining
    [120, 105, 90, 75, 60, 48, 35, 22, 12, 5],
    [80, 72, 65, 58, 50, 42, 32, 22, 14, 4],
    [160, 140, 120, 100, 80, 60, 45, 30, 18, 6],
    # 3 Rising
    [10, 18, 28, 40, 55, 72, 88, 105, 125, 145],
    [5, 12, 20, 32, 45, 60, 76, 92, 110, 130],
    [15, 25, 35, 48, 62, 78, 95, 112, 130, 150],
    # 3 Flat
    [50, 52, 49, 51, 50, 48, 52, 50, 49, 51],
    [75, 74, 76, 75, 73, 75, 76, 74, 75, 75],
    [30, 31, 29, 30, 32, 30, 29, 31, 30, 30],
    # 2 Alternating High / Low
    [15, 95, 18, 90, 12, 88, 14, 92, 16, 85],
    [85, 20, 80, 18, 88, 15, 82, 22, 78, 16],
    # 1 All-Zero (Causal Dormancy Rule)
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]


def build_classify_sample() -> Dict[str, Any]:
    """
    Constructs and validates the 120-record sample request payload for POST /classify.
    Returns:
      {"records": [BehaviorRecord...], "week": 9}
    """
    course_id = "DEMO_C2"
    records_list: List[Dict[str, Any]] = []

    for s_idx, pattern in enumerate(PATTERNS):
        pid = make_pid(s_idx)
        for w, clicks in enumerate(pattern):
            # Realistic assessment timing: submission on weeks 2, 5, 8 if student was active
            has_sub = 1 if (w in (2, 5, 8) and clicks > 0) else 0
            delay = 2.5 if has_sub else 0.0

            rec_dict = {
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "login_count": 0,
                "session_minutes": 0.0,
                "clicks": clicks,
                "video_play_count": 0,
                "video_pause_count": 0,
                "video_rewind_count": 0,
                "video_skip_count": 0,
                "video_completion_pct": 0.0,
                "submissions_count": has_sub,
                "avg_submission_delay_hours": delay,
            }

            # Schema validation check
            validated = BehaviorRecord.model_validate(rec_dict)
            records_list.append(validated.model_dump())

    return {
        "records": records_list,
        "week": 9,
    }


def main() -> None:
    sample_data = build_classify_sample()
    out_dir = COMPONENT_ROOT / "reports" / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "classify_request_sample.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)

    print(f"Successfully generated {len(sample_data['records'])} records for 12 students to {out_path}.")


if __name__ == "__main__":
    main()
