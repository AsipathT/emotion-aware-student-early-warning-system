"""
Command-line runner for fetching weekly student behavior, predicting trajectories,
and conditionally posting to the LMS ingest API.
"""

import argparse
import sys
from pathlib import Path

# Ensure components/c2-behavioral is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import joblib

from service.lms_client import LmsClient
from service.pipeline import classify_records
from service.schemas import build_envelope
from service.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Component 2 weekly trajectory classification and ingest."
    )
    parser.add_argument("--course-id", required=True, help="Course identifier (e.g. AAA_2013J)")
    parser.add_argument("--week", type=int, default=None, help="Target week index (optional)")
    parser.add_argument(
        "--send",
        action="store_true",
        help="If set, post trajectories to /api/v1/ingest/trajectory; otherwise only print summary",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Run ingest in dry_run mode (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Run ingest in live write mode",
    )

    args = parser.parse_args()

    # 1. Check API Key
    if not settings.C2_COMPONENT_KEY or not settings.C2_COMPONENT_KEY.strip():
        sys.stderr.write("ERROR: C2_COMPONENT_KEY is missing or empty. Ingest auth requires a key.\n")
        sys.exit(1)

    # 2. Check model file
    model_path = settings.C2_MODEL_PATH
    if not model_path.is_file():
        sys.stderr.write(f"ERROR: Model file not found at {model_path}.\n")
        sys.exit(1)

    bundle = joblib.load(model_path)

    # 3. Fetch weekly behavior records
    print(f"Fetching behavior records for course: '{args.course_id}'...")
    with LmsClient(settings.LMS_BASE_URL, settings.C2_COMPONENT_KEY) as client:
        records = client.fetch_behavior(course_id=args.course_id, week_to=args.week)
    print(f"  Fetched {len(records):,} weekly behavior records.")

    # 4. Classify records
    print("Classifying behavioral engagement trajectories...")
    traj_records, stats = classify_records(records, bundle, target_week=args.week)
    envelope = build_envelope(traj_records)

    # 5. Print stats table
    print("\n" + "=" * 65)
    print("CLASSIFICATION PIPELINE SUMMARY")
    print("=" * 65)
    print(f"  Received student-course groups: {stats['received_groups']:,}")
    print(f"  Classified trajectories:        {stats['classified']:,}")
    print(f"  Skipped - Cold start (<4 weeks): {stats['skipped']['cold_start']:,}")
    print(f"  Skipped - No row for week:       {stats['skipped']['no_row_for_week']:,}")
    print(f"  Skipped - Processing errors:     {stats['skipped']['error']:,}")
    print("-" * 65)
    print("  Predicted Trajectory Labels:")
    for lbl, count in stats["label_counts"].items():
        print(f"    {lbl:<12}: {count:,}")
    print("=" * 65)

    # 6. Post if --send flag is set
    if not args.send:
        print("\nNotice: --send flag not passed. Envelope was NOT posted to LMS ingest.")
        return

    print(f"\nSending {len(traj_records):,} trajectories to LMS ingest (dry_run={args.dry_run})...")
    with LmsClient(settings.LMS_BASE_URL, settings.C2_COMPONENT_KEY) as client:
        ingest_res = client.post_trajectory(envelope, dry_run=args.dry_run)

    print("\n" + "=" * 65)
    print("LMS INGEST RESPONSE SUMMARY")
    print("=" * 65)
    print(f"  Run ID:    {ingest_res.get('run_id')}")
    print(f"  Dry run:   {ingest_res.get('dry_run')}")
    print(f"  Received:  {ingest_res.get('received', 0):,}")
    print(f"  Accepted:  {ingest_res.get('accepted', 0):,}")
    print(f"  Rejected:  {ingest_res.get('rejected', 0):,}")
    print(f"  Created:   {ingest_res.get('created', 0):,}")
    print(f"  Updated:   {ingest_res.get('updated', 0):,}")

    rejected = ingest_res.get("rejected_records", [])
    if rejected:
        print("-" * 65)
        print("  Rejection reasons breakdown:")
        reason_counts = {}
        for r in rejected:
            rc = r.get("reason_code", "UNKNOWN")
            reason_counts[rc] = reason_counts.get(rc, 0) + 1
        for rc, cnt in reason_counts.items():
            print(f"    {rc}: {cnt:,}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
