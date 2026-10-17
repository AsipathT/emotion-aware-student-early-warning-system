"""
scripts/audit_oulad.py

Audits OULAD CSV files, computes dataset distributions, verifies trajectory
labeling assumptions, prints a summary table to stdout, and writes
reports/metrics/data_audit.json.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Set, Tuple

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import pandas as pd

from src.config import KEYS, component_root, get_oulad_dir


def run_audit() -> Dict[str, Any]:
    """Computes all audit metrics on OULAD CSV dataset and returns summary dict."""
    oulad_dir = get_oulad_dir()
    print(f"Starting OULAD data audit from: {oulad_dir}")

    # ── 1. Read Small CSV Files ───────────────────────────────────────────────
    print("Loading metadata CSV files...")
    courses = pd.read_csv(oulad_dir / "courses.csv")
    assessments = pd.read_csv(oulad_dir / "assessments.csv")
    student_assessment = pd.read_csv(oulad_dir / "studentAssessment.csv")
    student_info = pd.read_csv(oulad_dir / "studentInfo.csv")
    student_reg = pd.read_csv(oulad_dir / "studentRegistration.csv")
    vle = pd.read_csv(oulad_dir / "vle.csv")

    # ── 2. Process studentVle.csv in Chunks (450 MB) ───────────────────────────
    print("Streaming studentVle.csv in chunks of 1,000,000 rows...")
    chunk_size = 1_000_000
    vle_rows_count: int = 0
    vle_date_min: int | None = None
    vle_date_max: int | None = None
    vle_total_clicks: int = 0
    vle_precourse_clicks: int = 0
    vle_week0_clicks: int = 0

    info_keys_tuples: list[Tuple[Any, ...]] = list(
        student_info[KEYS].itertuples(index=False, name=None)
    )
    info_keys_set: Set[Tuple[Any, ...]] = set(info_keys_tuples)
    vle_keys_seen: Set[Tuple[Any, ...]] = set()

    vle_chunks = pd.read_csv(
        oulad_dir / "studentVle.csv",
        usecols=["code_module", "code_presentation", "id_student", "date", "sum_click"],
        dtype={"id_student": "int32", "date": "int16", "sum_click": "int32"},
        chunksize=chunk_size,
    )

    for chunk_idx, chunk in enumerate(vle_chunks, start=1):
        vle_rows_count += len(chunk)

        # Min and max date
        c_min = int(chunk["date"].min())
        c_max = int(chunk["date"].max())
        vle_date_min = c_min if vle_date_min is None else min(vle_date_min, c_min)
        vle_date_max = c_max if vle_date_max is None else max(vle_date_max, c_max)

        # Click sums
        vle_total_clicks += int(chunk["sum_click"].sum())

        precourse_mask = chunk["date"] < 0
        vle_precourse_clicks += int(chunk.loc[precourse_mask, "sum_click"].sum())

        week0_mask = chunk["date"] < 7
        vle_week0_clicks += int(chunk.loc[week0_mask, "sum_click"].sum())

        # Track distinct student enrollment keys seen in VLE
        unique_chunk_keys = chunk[KEYS].drop_duplicates()
        chunk_tuples = set(unique_chunk_keys.itertuples(index=False, name=None))
        vle_keys_seen.update(chunk_tuples.intersection(info_keys_set))

    # ── 3. Compute Metrics ────────────────────────────────────────────────────
    print("Computing metrics and distributions...")

    # Row counts
    rows: Dict[str, int] = {
        "assessments.csv": int(len(assessments)),
        "courses.csv": int(len(courses)),
        "studentAssessment.csv": int(len(student_assessment)),
        "studentInfo.csv": int(len(student_info)),
        "studentRegistration.csv": int(len(student_reg)),
        "studentVle.csv": int(vle_rows_count),
        "vle.csv": int(len(vle)),
    }

    # Student counts and outcomes
    final_result_counts: Dict[str, int] = {
        str(k): int(v) for k, v in student_info["final_result"].value_counts().items()
    }
    n_students_unique: int = int(student_info["id_student"].nunique())
    n_students_multi_presentation: int = int(
        (student_info["id_student"].value_counts() > 1).sum()
    )

    # Withdrawals & Registration merging
    merged_info_reg = pd.merge(student_info, student_reg, on=KEYS, how="inner")
    withdrawn_rows = merged_info_reg[merged_info_reg["final_result"] == "Withdrawn"]
    withdrawn_total: int = int(len(withdrawn_rows))
    withdrawn_without_unreg_date: int = int(
        withdrawn_rows["date_unregistration"].isna().sum()
    )
    unreg_date_negative: int = int((merged_info_reg["date_unregistration"] < 0).sum())

    # Precourse click shares
    vle_clicks_share_precourse: float = (
        float(vle_precourse_clicks / vle_total_clicks) if vle_total_clicks > 0 else 0.0
    )
    vle_week0_precourse_share: float = (
        float(vle_precourse_clicks / vle_week0_clicks) if vle_week0_clicks > 0 else 0.0
    )

    # Students with zero VLE activity
    students_without_vle_rows: int = sum(
        1 for k in info_keys_tuples if k not in vle_keys_seen
    )

    # Assessments
    assessments_by_type: Dict[str, int] = {
        str(k): int(v) for k, v in assessments["assessment_type"].value_counts().items()
    }
    assessments_date_nan: int = int(assessments["date"].isna().sum())
    banked_submissions: int = int(student_assessment["is_banked"].sum())

    # 2013 vs 2014 student overlap
    rows_2014 = student_info[
        student_info["code_presentation"].astype(str).str.startswith("2014")
    ]
    students_2013 = set(
        student_info.loc[
            student_info["code_presentation"].astype(str).str.startswith("2013"),
            "id_student",
        ]
    )
    overlap_2014_count = int(rows_2014["id_student"].isin(students_2013).sum())
    presentation_overlap_2014_rows_with_2013_student: float = (
        float(overlap_2014_count / len(rows_2014)) if len(rows_2014) > 0 else 0.0
    )

    courses_max_length_days: int = int(courses["module_presentation_length"].max())

    # Build exact results dictionary
    audit_results: Dict[str, Any] = {
        "rows": rows,
        "final_result_counts": final_result_counts,
        "n_students_unique": n_students_unique,
        "n_students_multi_presentation": n_students_multi_presentation,
        "withdrawn_total": withdrawn_total,
        "withdrawn_without_unreg_date": withdrawn_without_unreg_date,
        "unreg_date_negative": unreg_date_negative,
        "vle_date_min": int(vle_date_min) if vle_date_min is not None else 0,
        "vle_date_max": int(vle_date_max) if vle_date_max is not None else 0,
        "vle_clicks_share_precourse": vle_clicks_share_precourse,
        "vle_week0_precourse_share": vle_week0_precourse_share,
        "students_without_vle_rows": students_without_vle_rows,
        "assessments_by_type": assessments_by_type,
        "assessments_date_nan": assessments_date_nan,
        "banked_submissions": banked_submissions,
        "presentation_overlap_2014_rows_with_2013_student": presentation_overlap_2014_rows_with_2013_student,
        "courses_max_length_days": courses_max_length_days,
    }

    # ── 4. Print Summary Table ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("                      OULAD DATA AUDIT SUMMARY")
    print("=" * 70)
    print("\n[CSV Row Counts]")
    for fname, count in rows.items():
        print(f"  - {fname:<25}: {count:>12,}")

    print("\n[Student Demographics & Results]")
    print(f"  Unique students                  : {n_students_unique:>10,}")
    print(f"  Students in >1 presentation      : {n_students_multi_presentation:>10,}")
    print(f"  Students without any VLE rows    : {students_without_vle_rows:>10,}")
    print("  Outcome distribution:")
    for outcome, cnt in final_result_counts.items():
        print(f"    * {outcome:<20}: {cnt:>10,}")

    print("\n[Withdrawal Integrity]")
    print(f"  Withdrawn total                  : {withdrawn_total:>10,}")
    print(f"  Withdrawn without unreg date     : {withdrawn_without_unreg_date:>10,}")
    print(f"  Unregistration date < 0          : {unreg_date_negative:>10,}")

    print("\n[VLE Clickstream & Pre-Course Days]")
    print(f"  VLE date range                   : [{audit_results['vle_date_min']}, {audit_results['vle_date_max']}] days")
    print(f"  Pre-course clicks share (all)    : {vle_clicks_share_precourse * 100:>9.2f}%")
    print(f"  Pre-course share of Week 0 clicks: {vle_week0_precourse_share * 100:>9.2f}%")

    print("\n[Assessments & Calendar]")
    print(f"  Banked submissions               : {banked_submissions:>10,}")
    print(f"  Assessments with NaN date        : {assessments_date_nan:>10,}")
    print(f"  Max course length (days)         : {courses_max_length_days:>10}")
    print(f"  2014 rows with 2013 student      : {presentation_overlap_2014_rows_with_2013_student * 100:>9.2f}%")
    print("  Assessments by type:")
    for atype, cnt in assessments_by_type.items():
        print(f"    * {atype:<20}: {cnt:>10,}")
    print("=" * 70 + "\n")

    # ── 5. Write reports/metrics/data_audit.json ──────────────────────────────
    out_path = component_root() / "reports" / "metrics" / "data_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)
    print(f"Audit metrics successfully saved to: {out_path}")

    return audit_results


if __name__ == "__main__":
    run_audit()
