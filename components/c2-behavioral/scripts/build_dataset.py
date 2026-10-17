"""
scripts/build_dataset.py

Constructs the full Component 2 dataset:
1. Enrolment table with censoring logic (data/enrolment.pkl)
2. Weekly clicks and submissions aggregated from OULAD (data/weekly_dense.pkl)
3. 7-week centered engagement trajectory labels (data/labels.pkl)
"""

import sys
from pathlib import Path

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import pandas as pd

from src.config import component_root, get_oulad_dir
from src.enrolment import build_enrolment_table
from src.labels import compute_labels
from src.weekly import build_dense_weekly, load_weekly_clicks, load_weekly_submissions


def build_all() -> None:
    """Executes the dataset build pipeline and serializes outputs as pkl."""
    oulad_dir = get_oulad_dir()
    data_dir = component_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("           C2 BEHAVIORAL: BUILD DATASET PIPELINE")
    print("=" * 65)
    print(f"OULAD source: {oulad_dir}")
    print(f"Output path : {data_dir}\n")

    # 1. Enrolment table
    print("[1/4] Building enrolment table...")
    info = pd.read_csv(oulad_dir / "studentInfo.csv")
    reg = pd.read_csv(oulad_dir / "studentRegistration.csv")
    courses = pd.read_csv(oulad_dir / "courses.csv")
    enrolment_df = build_enrolment_table(info, reg, courses)
    enrol_path = data_dir / "enrolment.pkl"
    enrolment_df.to_pickle(enrol_path)
    print(f"      -> Enrolment records: {len(enrolment_df):,} saved to {enrol_path.name}")

    # 2. Weekly clicks & submissions
    print("\n[2/4] Aggregating weekly clicks and submissions...")
    clicks_df = load_weekly_clicks(oulad_dir)
    print(f"      -> Weekly click records: {len(clicks_df):,}")
    subs_df = load_weekly_submissions(oulad_dir)
    print(f"      -> Weekly submission records: {len(subs_df):,}")

    # 3. Dense weekly grid
    print("\n[3/4] Constructing dense weekly grid (censored and zero-filled)...")
    dense_df = build_dense_weekly(enrolment_df, clicks_df, subs_df)
    dense_path = data_dir / "weekly_dense.pkl"
    dense_df.to_pickle(dense_path)
    print(f"      -> Dense weekly records: {len(dense_df):,} saved to {dense_path.name}")

    # 4. Trajectory labels
    print("\n[4/4] Computing 7-week centered trajectory labels...")
    labels_df = compute_labels(dense_df)
    labels_path = data_dir / "labels.pkl"
    labels_df.to_pickle(labels_path)
    print(f"      -> Label records: {len(labels_df):,} saved to {labels_path.name}")

    print("\n" + "=" * 65)
    print("DATASET BUILD COMPLETED SUCCESSFULLY")
    print(f"  - enrolment.pkl    : {len(enrolment_df):>10,} rows")
    print(f"  - weekly_dense.pkl : {len(dense_df):>10,} rows")
    print(f"  - labels.pkl       : {len(labels_df):>10,} rows")
    print("=" * 65)


if __name__ == "__main__":
    build_all()
