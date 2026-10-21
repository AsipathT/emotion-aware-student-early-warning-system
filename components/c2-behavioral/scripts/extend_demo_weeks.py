"""
scripts/extend_demo_weeks.py

Extends synthetic longitudinal behavior_weekly and risk_assessments documents
for weeks 10 to 14 (week_index) for a given course so that the LMS Cohort Risk
dashboard displays UI weeks 11 to 15.

Does NOT write to engagement_trajectories (Component 2 handles trajectory
generation and ingest separately via scripts/run_week.py).
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import os
import random
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Canonical pattern definitions
PATTERNS = ["continue_decline", "recover", "flat", "volatile"]
PATTERN_WEIGHTS = [0.25, 0.20, 0.35, 0.20]


def parse_week_range(from_week: int, to_week: int) -> List[int]:
    """Parse and validate week_index integer range [from_week, to_week] inclusive."""
    if not isinstance(from_week, int) or not isinstance(to_week, int):
        raise ValueError(f"Week values must be integers. Got {type(from_week)} and {type(to_week)}")
    if from_week < 0 or to_week < 0:
        raise ValueError(f"Week indices cannot be negative: from_week={from_week}, to_week={to_week}")
    if from_week > to_week:
        raise ValueError(f"Invalid week range: from_week={from_week} is greater than to_week={to_week}")
    return list(range(from_week, to_week + 1))


def assign_student_pattern(seed: int, pid: str) -> str:
    """Deterministically assign a single pattern per student based on (seed + pid)."""
    h = int(hashlib.sha256(f"{seed}_{pid}".encode("utf-8")).hexdigest()[:15], 16)
    rng = random.Random(h)
    return rng.choices(PATTERNS, weights=PATTERN_WEIGHTS)[0]


def next_clicks(
    history_clicks: List[float | int],
    rng: random.Random,
    pattern: Optional[str] = None,
    step: int = 0,
) -> int:
    """
    Compute next week clicks from recent clicks history and pattern.

    - continue_decline: x0.8 per week
    - recover: x1.3 per week, capped at 120
    - flat: x(0.9 - 1.1)
    - volatile: alternates x0.5 and x1.8 based on step
    Returns non-negative integer >= 0.
    """
    prev_clicks = float(history_clicks[-1]) if history_clicks else 0.0

    if pattern is None:
        pattern = rng.choices(PATTERNS, weights=PATTERN_WEIGHTS)[0]

    if pattern == "continue_decline":
        raw = prev_clicks * 0.8
    elif pattern == "recover":
        base = prev_clicks if prev_clicks > 0 else 10.0
        raw = min(120.0, base * 1.3)
    elif pattern == "flat":
        raw = prev_clicks * rng.uniform(0.9, 1.1)
    elif pattern == "volatile":
        factor = 0.5 if (step % 2 == 0) else 1.8
        base = prev_clicks if prev_clicks > 0 else 10.0
        raw = base * factor
    else:
        raw = prev_clicks

    return max(0, int(round(raw)))


def build_behavior_doc(
    prev_doc: Dict[str, Any],
    week_index: int,
    clicks: int,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Create a new behavior_weekly document for week_index copying all fields of prev_doc.
    Scales numeric telemetry proportionally to clicks / prev_clicks while keeping
    submissions_count and avg_submission_delay_hours unchanged.
    """
    doc = dict(prev_doc)
    pid = str(prev_doc["pid"])
    course_id = str(prev_doc["course_id"])

    doc["_id"] = f"{pid}_{course_id}_{week_index}"
    doc["week_index"] = int(week_index)
    doc["clicks"] = int(clicks)
    doc["ingested_at"] = datetime.now(timezone.utc)
    doc["source"] = "synthetic"

    prev_clicks = float(prev_doc.get("clicks", 0))
    if prev_clicks > 0:
        ratio = float(clicks) / prev_clicks
    else:
        ratio = 1.0 if clicks == 0 else (float(clicks) / 10.0)

    # Scale login_count and session_minutes
    if "login_count" in prev_doc and isinstance(prev_doc["login_count"], (int, float)):
        doc["login_count"] = max(0, int(round(float(prev_doc["login_count"]) * ratio)))

    if "session_minutes" in prev_doc and isinstance(prev_doc["session_minutes"], (int, float)):
        doc["session_minutes"] = max(0.0, round(float(prev_doc["session_minutes"]) * ratio, 1))

    # Scale video_* fields
    for k, v in prev_doc.items():
        if k.startswith("video_") and isinstance(v, (int, float)):
            if k == "video_completion_pct":
                doc[k] = max(0.0, min(100.0, round(float(v) * ratio, 1)))
            elif isinstance(v, int):
                doc[k] = max(0, int(round(float(v) * ratio)))
            else:
                doc[k] = max(0.0, round(float(v) * ratio, 1))

    # Submissions and delay remain unchanged
    if "submissions_count" in prev_doc:
        doc["submissions_count"] = prev_doc["submissions_count"]
    if "avg_submission_delay_hours" in prev_doc:
        doc["avg_submission_delay_hours"] = prev_doc["avg_submission_delay_hours"]

    return doc


def build_risk_doc(prev_doc: Dict[str, Any], week_index: int) -> Dict[str, Any]:
    """
    Create a new risk_assessments document for week_index copying all risk fields
    from prev_doc. Ensures modality_contributions sum to 1.0.
    """
    doc = dict(prev_doc)
    pid = str(prev_doc["pid"])
    course_id = str(prev_doc["course_id"])

    doc["_id"] = f"{pid}_{course_id}_{week_index}"
    doc["week_index"] = int(week_index)
    doc["ingested_at"] = datetime.now(timezone.utc)
    doc["source"] = "synthetic"

    # Preserved risk metrics
    doc["risk_score"] = prev_doc.get("risk_score", 0.0)
    doc["risk_tier"] = prev_doc.get("risk_tier", "low")
    doc["top_drivers"] = list(prev_doc.get("top_drivers", []))

    # Normalize modality contributions if present so they sum strictly to 1.0
    mods = dict(prev_doc.get("modality_contributions", {}))
    if not mods:
        mods = {"affective": 0.33, "behavioral": 0.34, "academic": 0.33}
    else:
        tot = sum(mods.values())
        if tot > 0 and abs(tot - 1.0) > 1e-6:
            keys = list(mods.keys())
            mods = {k: round(v / tot, 3) for k, v in mods.items()}
            diff = round(1.0 - sum(mods.values()), 3)
            mods[keys[-1]] = round(mods[keys[-1]] + diff, 3)
    doc["modality_contributions"] = mods

    return doc


def select_missing(
    existing_keys: Set[Tuple[str, str, int]],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter out candidate documents whose (pid, course_id, week_index) already exists."""
    missing = []
    for doc in candidates:
        key = (str(doc["pid"]), str(doc["course_id"]), int(doc["week_index"]))
        if key not in existing_keys:
            missing.append(doc)
    return missing


def validate_live_args(course_id: str, confirm_course: Optional[str], dry_run: bool) -> None:
    """Validate safety guard for live writes."""
    if not dry_run:
        if not confirm_course or confirm_course != course_id:
            raise ValueError(
                f"Live write requires --confirm-course matching --course-id ('{course_id}'). Got: '{confirm_course}'"
            )


def get_mongo_db():
    """Lazy MongoDB connection to prevent import errors in environments without pymongo."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri or not mongo_uri.strip():
        sys.exit("ERROR: MONGO_URI environment variable is not set. Set it in your terminal session; do not hard-code it.")

    try:
        from pymongo import MongoClient
    except ImportError:
        sys.exit("ERROR: pymongo is not installed. Please run this script in an environment with pymongo.")

    print("Connecting to MongoDB Atlas...")
    client = MongoClient(mongo_uri)
    return client, client["lms_db"]


def main():
    parser = argparse.ArgumentParser(
        description="Extend synthetic behavior and risk assessments for weeks 10 to 14."
    )
    parser.add_argument(
        "--course-id",
        required=True,
        type=str,
        help="Target course identifier (e.g. CS101, DEMO101)",
    )
    parser.add_argument(
        "--from-week",
        type=int,
        default=10,
        help="Initial week_index to generate (default: 10)",
    )
    parser.add_argument(
        "--to-week",
        type=int,
        default=14,
        help="Final week_index to generate (default: 14)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Deterministic random seed (default: 2026)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Simulate generation without writing to MongoDB (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Perform live database insertions",
    )
    parser.add_argument(
        "--confirm-course",
        type=str,
        default=None,
        help="Course ID confirmation required for live writes",
    )

    args = parser.parse_args()

    try:
        validate_live_args(args.course_id, args.confirm_course, args.dry_run)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    try:
        weeks = parse_week_range(args.from_week, args.to_week)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    client, db = get_mongo_db()

    # 1. Fetch prior behavior_weekly documents
    beh_cursor = db["behavior_weekly"].find(
        {"course_id": args.course_id, "week_index": {"$lt": args.from_week}}
    ).sort("week_index", 1)

    beh_by_pid = defaultdict(list)
    for doc in beh_cursor:
        beh_by_pid[doc["pid"]].append(doc)

    if not beh_by_pid:
        client.close()
        sys.exit(
            f"ERROR: Course '{args.course_id}' has no behavior_weekly documents with week_index < {args.from_week}."
        )

    # 2. Fetch prior risk_assessments documents
    ra_cursor = db["risk_assessments"].find(
        {"course_id": args.course_id, "week_index": {"$lt": args.from_week}}
    ).sort("week_index", 1)

    ra_by_pid = defaultdict(list)
    for doc in ra_cursor:
        ra_by_pid[doc["pid"]].append(doc)

    if not ra_by_pid:
        client.close()
        sys.exit(
            f"ERROR: Course '{args.course_id}' has no risk_assessments documents with week_index < {args.from_week}."
        )

    # 3. Generate candidate documents
    candidate_beh: List[Dict[str, Any]] = []
    candidate_ra: List[Dict[str, Any]] = []

    print(f"Generating data for {len(beh_by_pid)} students across weeks {weeks}...")

    for pid, b_list in sorted(beh_by_pid.items()):
        pattern = assign_student_pattern(args.seed, pid)
        latest_beh = b_list[-1]
        history_clicks = [d.get("clicks", 0) for d in b_list][-6:]

        # Student latest risk doc
        if pid in ra_by_pid and ra_by_pid[pid]:
            latest_ra = ra_by_pid[pid][-1]
        else:
            latest_ra = list(ra_by_pid.values())[0][-1]

        curr_beh = latest_beh
        for step_idx, w in enumerate(weeks):
            step_h = int(hashlib.sha256(f"{args.seed}_{pid}_{w}".encode("utf-8")).hexdigest()[:15], 16)
            step_rng = random.Random(step_h)

            next_c = next_clicks(history_clicks, step_rng, pattern=pattern, step=step_idx)
            b_doc = build_behavior_doc(curr_beh, w, next_c, step_rng)
            r_doc = build_risk_doc(latest_ra, w)

            candidate_beh.append(b_doc)
            candidate_ra.append(r_doc)

            curr_beh = b_doc
            history_clicks.append(next_c)

    # 4. Check existence and select missing
    existing_beh = db["behavior_weekly"].find(
        {"course_id": args.course_id, "week_index": {"$in": weeks}},
        {"pid": 1, "course_id": 1, "week_index": 1},
    )
    existing_beh_keys = {(d["pid"], d["course_id"], d["week_index"]) for d in existing_beh}
    to_insert_beh = select_missing(existing_beh_keys, candidate_beh)
    skipped_beh = len(candidate_beh) - len(to_insert_beh)

    existing_ra = db["risk_assessments"].find(
        {"course_id": args.course_id, "week_index": {"$in": weeks}},
        {"pid": 1, "course_id": 1, "week_index": 1},
    )
    existing_ra_keys = {(d["pid"], d["course_id"], d["week_index"]) for d in existing_ra}
    to_insert_ra = select_missing(existing_ra_keys, candidate_ra)
    skipped_ra = len(candidate_ra) - len(to_insert_ra)

    # 5. Output / Insert
    if args.dry_run:
        print("\n=== DRY RUN MODE (no writes performed) ===")
        print(f"Collection 'behavior_weekly': {len(to_insert_beh)} would be inserted, {skipped_beh} skipped.")
        print("Sample behavior_weekly docs (up to 3):")
        for s in to_insert_beh[:3]:
            s_clean = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in s.items()}
            print("  ", s_clean)

        print(f"\nCollection 'risk_assessments': {len(to_insert_ra)} would be inserted, {skipped_ra} skipped.")
        print("Sample risk_assessments docs (up to 3):")
        for s in to_insert_ra[:3]:
            s_clean = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in s.items()}
            print("  ", s_clean)
    else:
        print("\n=== LIVE WRITE MODE ===")
        inserted_beh = 0
        inserted_ra = 0
        if to_insert_beh:
            res_b = db["behavior_weekly"].insert_many(to_insert_beh)
            inserted_beh = len(res_b.inserted_ids)
        if to_insert_ra:
            res_r = db["risk_assessments"].insert_many(to_insert_ra)
            inserted_ra = len(res_r.inserted_ids)

        print(f"Inserted into 'behavior_weekly': {inserted_beh} (skipped: {skipped_beh})")
        print(f"Inserted into 'risk_assessments': {inserted_ra} (skipped: {skipped_ra})")

    client.close()

    print("\nNext command to generate C2 trajectories for these weeks:")
    for w in weeks:
        print(f"python scripts/run_week.py --course-id {args.course_id} --week {w} --send --no-dry-run")


if __name__ == "__main__":
    main()
