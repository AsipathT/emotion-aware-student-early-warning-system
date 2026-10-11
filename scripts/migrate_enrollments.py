#!/usr/bin/env python3
"""
scripts/migrate_enrollments.py

Feature 21 (Part A): Enrolment Migration Script.
Copies legacy documents from 'enrollments' to the canonical 'enrolments' collection.
- Maps legacy student_id -> user record -> PID.
- Skips and reports rows whose user has no PID or does not exist.
- Idempotent: safe to run multiple times without creating duplicate records.
- Never deletes or modifies the legacy 'enrollments' collection.
- Supports --dry-run flag.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup import path for both host and container environments
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
for candidate in [
    Path("/app"),
    project_root / "backend",
    project_root,
    current_dir,
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from pymongo import MongoClient
from app.core.config import settings
from app.db import collections as col


def migrate_enrollments(
    mongo_uri: str,
    db_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Executes the migration from 'enrollments' to 'enrolments'.
    Returns migration statistics.
    """
    client = MongoClient(mongo_uri, tz_aware=True)
    db = client[db_name]

    stats = {
        "legacy_found": 0,
        "copied": 0,
        "already_existing": 0,
        "skipped_no_user": 0,
        "skipped_no_pid": 0,
        "skipped_details": [],
        "dry_run": dry_run,
    }

    try:
        legacy_coll = db["enrollments"]
        canonical_coll = db[col.ENROLMENTS]

        legacy_docs = list(legacy_coll.find({}))
        stats["legacy_found"] = len(legacy_docs)

        if not legacy_docs:
            print("No documents found in legacy 'enrollments' collection.")
            return stats

        print(f"Found {len(legacy_docs)} legacy enrollment records to process.")

        # Pre-cache users to minimize database round-trips
        users = list(db["users"].find({}))
        user_by_id: Dict[str, Dict[str, Any]] = {}
        user_by_student_id: Dict[str, Dict[str, Any]] = {}
        for u in users:
            uid = str(u.get("_id", ""))
            alt_id = str(u.get("id", ""))
            stu_id = str(u.get("student_id", ""))
            if uid:
                user_by_id[uid] = u
            if alt_id:
                user_by_id[alt_id] = u
            if stu_id:
                user_by_student_id[stu_id] = u

        for doc in legacy_docs:
            raw_sid = str(doc.get("student_id", "")).strip()
            course_id = str(doc.get("course_id", "")).strip()
            legacy_id = str(doc.get("_id", doc.get("id", "")))

            # Lookup student user
            user = user_by_id.get(raw_sid) or user_by_student_id.get(raw_sid)
            if not user:
                stats["skipped_no_user"] += 1
                stats["skipped_details"].append({
                    "legacy_id": legacy_id,
                    "student_id": raw_sid,
                    "course_id": course_id,
                    "reason": "User not found in users collection",
                })
                continue

            pid = user.get("pid")
            if not pid:
                stats["skipped_no_pid"] += 1
                stats["skipped_details"].append({
                    "legacy_id": legacy_id,
                    "student_id": raw_sid,
                    "course_id": course_id,
                    "reason": "User exists but has no pseudonym identifier (PID)",
                })
                continue

            # Check if canonical enrolment already exists
            existing = canonical_coll.find_one({"pid": pid, "course_id": course_id})
            if existing:
                stats["already_existing"] += 1
                continue

            # Resolve start datetime
            raw_time = doc.get("enrolled_at") or doc.get("created_at") or datetime.now(timezone.utc)
            if isinstance(raw_time, datetime):
                if raw_time.tzinfo is None:
                    start_dt = raw_time.replace(tzinfo=timezone.utc)
                else:
                    start_dt = raw_time.astimezone(timezone.utc)
            else:
                start_dt = datetime.now(timezone.utc)

            new_enr_doc = {
                "_id": f"{pid}_{course_id}",
                "pid": pid,
                "course_id": course_id,
                "enrolment_start": start_dt,
                "status": doc.get("status", "active"),
                "schema_version": 1,
                "ingested_at": datetime.now(timezone.utc),
                "source_version": "1.0",
            }

            if not dry_run:
                canonical_coll.insert_one(new_enr_doc)

            stats["copied"] += 1

        print("\n════════════════════════════════════════════════════════════════")
        print("ENROLMENT MIGRATION REPORT")
        print("════════════════════════════════════════════════════════════════")
        print(f"  Mode:                         {'DRY RUN (no changes written)' if dry_run else 'LIVE EXECUTION'}")
        print(f"  Legacy documents found:       {stats['legacy_found']}")
        print(f"  Successfully copied:          {stats['copied']}")
        print(f"  Already existing in enrolments: {stats['already_existing']}")
        print(f"  Skipped (user not found):     {stats['skipped_no_user']}")
        print(f"  Skipped (user has no PID):    {stats['skipped_no_pid']}")
        print(f"  Old collection 'enrollments': PRESERVED INTACT (never deleted)")
        print("════════════════════════════════════════════════════════════════\n")

        return stats
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy enrollments to canonical enrolments.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and simulate migration without writing.")
    parser.add_argument("--mongo-uri", default=None, help="Override MongoDB connection URI.")
    parser.add_argument("--db-name", default=None, help="Override database name.")

    args = parser.parse_args()
    uri = args.mongo_uri or settings.MONGODB_URI
    db_name = args.db_name or settings.DB_NAME

    migrate_enrollments(mongo_uri=uri, db_name=db_name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
