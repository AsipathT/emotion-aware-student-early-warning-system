"""
scripts/label_report.py

Loads serialized labels and enrolment tables, evaluates label distributions,
computes dormant and trajectory class shares across demographic and course dimensions,
prints a summary report, and saves reports/metrics/label_report.json.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import pandas as pd

from src.config import KEYS, component_root


def generate_report() -> Dict[str, Any]:
    """Generates engagement trajectory label statistics and exports JSON report."""
    root = component_root()
    data_dir = root / "data"
    enrol_path = data_dir / "enrolment.pkl"
    labels_path = data_dir / "labels.pkl"

    if not enrol_path.exists() or not labels_path.exists():
        raise FileNotFoundError(
            f"Missing required dataset file(s). Please run scripts/build_dataset.py first.\n"
            f"Expected: {enrol_path} and {labels_path}"
        )

    print("Loading data/enrolment.pkl and data/labels.pkl...")
    enrolment: pd.DataFrame = pd.read_pickle(enrol_path)
    labels: pd.DataFrame = pd.read_pickle(labels_path)

    # 1. Excluded by reason
    excluded_rows = enrolment[enrolment["excluded"]]
    excluded_by_reason: Dict[str, int] = {
        str(k): int(v) for k, v in excluded_rows["exclude_reason"].value_counts().items()
    }

    # 2. Window and student counts
    n_students_with_windows: int = int(labels[KEYS].drop_duplicates().shape[0])
    n_windows_total: int = int(len(labels))
    n_windows_dormant: int = int((labels["dormant"] == True).sum())
    dormant_share: float = (
        float(n_windows_dormant / n_windows_total) if n_windows_total > 0 else 0.0
    )

    # 3. Non-dormant label distribution
    non_dormant = labels[~labels["dormant"]]
    label_counts_nondormant: Dict[str, int] = {
        str(k): int(v) for k, v in non_dormant["label"].value_counts().items()
    }
    label_share_nondormant: Dict[str, float] = {
        str(k): float(v) for k, v in non_dormant["label"].value_counts(normalize=True).items()
    }

    # 4. Dormant share by final_result outcome
    dormant_share_by_outcome: Dict[str, float] = {}
    for outcome, grp in labels.groupby("final_result"):
        dormant_share_by_outcome[str(outcome)] = (
            float((grp["dormant"] == True).sum() / len(grp)) if len(grp) > 0 else 0.0
        )

    # 5. Declining share by outcome among non-dormant windows
    declining_share_by_outcome: Dict[str, float] = {}
    for outcome, grp in non_dormant.groupby("final_result"):
        declining_share_by_outcome[str(outcome)] = (
            float((grp["label"] == "declining").sum() / len(grp)) if len(grp) > 0 else 0.0
        )

    # 6. Non-dormant label share by module
    label_share_by_module_nondormant: Dict[str, Dict[str, float]] = {}
    for mod, grp in non_dormant.groupby("code_module"):
        label_share_by_module_nondormant[str(mod)] = {
            str(lbl): float(sh)
            for lbl, sh in grp["label"].value_counts(normalize=True).items()
        }

    # 7. Non-dormant label share by presentation
    label_share_by_presentation_nondormant: Dict[str, Dict[str, float]] = {}
    for pres, grp in non_dormant.groupby("code_presentation"):
        label_share_by_presentation_nondormant[str(pres)] = {
            str(lbl): float(sh)
            for lbl, sh in grp["label"].value_counts(normalize=True).items()
        }

    # Assemble report dictionary with exact required keys
    report_data: Dict[str, Any] = {
        "excluded_by_reason": excluded_by_reason,
        "n_students_with_windows": n_students_with_windows,
        "n_windows_total": n_windows_total,
        "n_windows_dormant": n_windows_dormant,
        "dormant_share": dormant_share,
        "label_counts_nondormant": label_counts_nondormant,
        "label_share_nondormant": label_share_nondormant,
        "dormant_share_by_outcome": dormant_share_by_outcome,
        "declining_share_by_outcome": declining_share_by_outcome,
        "label_share_by_module_nondormant": label_share_by_module_nondormant,
        "label_share_by_presentation_nondormant": label_share_by_presentation_nondormant,
    }

    # Print summary table
    print("\n" + "=" * 68)
    print("                C2 TRAJECTORY LABEL AUDIT REPORT")
    print("=" * 68)
    print("\n[Enrolment Censoring & Exclusions]")
    for reason, count in excluded_by_reason.items():
        print(f"  - {reason:<28}: {count:>10,}")

    print("\n[Window & Student Counts]")
    print(f"  Students with valid windows     : {n_students_with_windows:>10,}")
    print(f"  Total observation windows       : {n_windows_total:>10,}")
    print(f"  Dormant windows (zero clicks)   : {n_windows_dormant:>10,} ({dormant_share * 100:.2f}%)")
    print(f"  Active non-dormant windows      : {len(non_dormant):>10,}")

    print("\n[Non-Dormant Trajectory Distribution]")
    for lbl, count in label_counts_nondormant.items():
        share = label_share_nondormant.get(lbl, 0.0)
        print(f"  * {lbl:<12}: {count:>10,} ({share * 100:>6.2f}%)")

    print("\n[Dormant & Declining Share by Final Result]")
    all_outcomes = sorted(
        list(set(dormant_share_by_outcome.keys()) | set(declining_share_by_outcome.keys()))
    )
    print(f"  {'Outcome':<16} {'Dormant %':>12} {'Declining % (Non-dormant)':>26}")
    print("  " + "-" * 56)
    for out in all_outcomes:
        d_sh = dormant_share_by_outcome.get(out, 0.0) * 100
        dec_sh = declining_share_by_outcome.get(out, 0.0) * 100
        print(f"  {out:<16} {d_sh:>11.2f}% {dec_sh:>25.2f}%")

    print("=" * 68 + "\n")

    # Save to reports/metrics/label_report.json
    out_path = root / "reports" / "metrics" / "label_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Label report successfully saved to: {out_path}")

    return report_data


if __name__ == "__main__":
    generate_report()
