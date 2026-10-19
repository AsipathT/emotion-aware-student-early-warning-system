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
from service.plotting import plot_trajectories
from service.schemas import build_envelope
from service.settings import settings


def format_show_table(rows: list[dict]) -> str:
    """
    Format classified student trajectory records into a readable text table.

    Columns:
      pid_suffix (last 4 chars) | clicks for the last 6 weeks as a compact list (e.g. 12,9,7,3,0,0) | trajectory_label | confidence (2 decimals) | indicators joined by ","
    """
    header = "pid_suffix | clicks_last_6w | trajectory_label | confidence | indicators"
    separator = "-" * len(header)
    lines = [header, separator]

    for r in rows:
        pid_raw = str(r.get("pid_suffix") or r.get("pid") or "")
        pid_suffix = pid_raw[-4:] if len(pid_raw) >= 4 else pid_raw

        clicks_raw = r.get("clicks", [])
        if isinstance(clicks_raw, (list, tuple)):
            clicks_str = ",".join(str(int(c)) for c in clicks_raw)
        else:
            clicks_str = str(clicks_raw)

        label = str(r.get("trajectory_label", ""))

        conf_raw = r.get("confidence", 0.0)
        try:
            conf_str = f"{float(conf_raw):.2f}"
        except (ValueError, TypeError):
            conf_str = str(conf_raw)

        ind_raw = r.get("indicators")
        if ind_raw is None:
            ind_raw = r.get("contributing_indicators", [])
        if isinstance(ind_raw, (list, tuple)):
            ind_str = ",".join(str(x) for x in ind_raw)
        else:
            ind_str = str(ind_raw)

        lines.append(f"{pid_suffix} | {clicks_str} | {label} | {conf_str} | {ind_str}")

    return "\n".join(lines)


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
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
        help="Print classified student trajectories table (sorted by pid)",
    )
    parser.add_argument(
        "--plot",
        metavar="PATH",
        default=None,
        help="Path to save trajectories plot PNG (optional)",
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

    # 5b. Print per-student trajectory table if --show is set
    if args.show:
        clicks_by_pid_week: dict[str, dict[int, int]] = {}
        for r in records:
            if r.pid not in clicks_by_pid_week:
                clicks_by_pid_week[r.pid] = {}
            clicks_by_pid_week[r.pid][r.week_index] = int(r.clicks)

        show_rows = []
        for traj in traj_records:
            t = traj.week_index
            hist = clicks_by_pid_week.get(traj.pid, {})
            clicks_6w = [hist.get(w, 0) for w in range(t - 5, t + 1)]
            show_rows.append(
                {
                    "pid": traj.pid,
                    "clicks": clicks_6w,
                    "trajectory_label": traj.trajectory_label,
                    "confidence": traj.confidence,
                    "indicators": traj.contributing_indicators,
                }
            )

        show_rows.sort(key=lambda item: item["pid"])
        print("\n" + "=" * 65)
        print("CLASSIFIED STUDENT TRAJECTORIES (--show)")
        print("=" * 65)
        print(format_show_table(show_rows))
        print("=" * 65)

    # 5c. Plot trajectories if --plot is set
    if args.plot:
        t = args.week if args.week is not None else (traj_records[0].week_index if traj_records else 0)
        plot_trajectories(records, traj_records, args.plot, f"Component 2 trajectories, course {args.course_id}, week {t}")
        print(f"Saved plot: {args.plot}")

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
