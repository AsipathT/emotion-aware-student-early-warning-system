#!/usr/bin/env python3
"""
scripts/verify_integrity.py

Feature 25: High-Performance Database Referential Integrity Verification Script.
Executes set-difference and aggregation-based integrity checks across collections:
1. Every PID in enrolments exists in identity_vault.
2. Every course_id in enrolments exists in courses.
3. Every (pid, course_id) in each weekly collection has an enrolment record.
4. Analytics collections contain NO forbidden fields (student_id, registration_id, name, email)
   and all PIDs adhere to the Feature 5 regex format (^STU_[0-9a-fA-F]{8}$).

Designed for scale: Uses distinct/aggregations, never individual document loops.
Exits with non-zero code on any detected violation.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Setup sys.path so app modules import cleanly in both host and Docker container environments
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

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import create_mongo_client
from app.db.collections import (
    ANALYTICS_COLLECTIONS,
    COURSES,
    ENROLMENTS,
    IDENTITY_VAULT,
    WEEKLY_COLLECTIONS,
)
from app.core.privacy import PID_REGEX


async def verify_integrity(
    db: AsyncIOMotorDatabase,
    sample_size: int | None = None,
) -> Tuple[bool, List[str]]:
    """
    Runs all 4 database integrity checks.
    Returns (is_healthy: bool, violations: List[str]).
    """
    violations: List[str] = []

    print(f"Starting integrity verification on database '{db.name}'...")

    # ── Check 1: Enrolment PIDs exist in Identity Vault ───────────────────────
    enrolment_pids = set(await db[ENROLMENTS].distinct("pid"))
    vault_pids = set(await db[IDENTITY_VAULT].distinct("pid"))
    orphan_pids = enrolment_pids - vault_pids

    if orphan_pids:
        sample = sorted(list(orphan_pids))[:5]
        violations.append(
            f"Check 1 Failed: {len(orphan_pids)} enrolment PID(s) missing from identity_vault. Sample: {sample}"
        )
    else:
        print(f"  [PASS] Check 1: All {len(enrolment_pids)} enrolment PIDs exist in identity_vault.")

    # ── Check 2: Enrolment Course IDs exist in Courses ────────────────────────
    enrolment_courses = set(await db[ENROLMENTS].distinct("course_id"))
    course_ids = set(await db[COURSES].distinct("course_id"))
    orphan_courses = enrolment_courses - course_ids

    if orphan_courses:
        sample = sorted(list(orphan_courses))[:5]
        violations.append(
            f"Check 2 Failed: {len(orphan_courses)} enrolment course_id(s) missing from courses. Sample: {sample}"
        )
    else:
        print(f"  [PASS] Check 2: All {len(enrolment_courses)} enrolment courses exist in courses.")

    # ── Check 3: Weekly records have corresponding Enrolments ─────────────────
    # Aggregate all (pid, course_id) tuples in enrolments
    enrolment_pairs: Set[Tuple[str, str]] = set()
    async for doc in db[ENROLMENTS].aggregate([
        {"$group": {"_id": {"pid": "$pid", "course_id": "$course_id"}}}
    ]):
        if doc.get("_id"):
            enrolment_pairs.add((doc["_id"].get("pid"), doc["_id"].get("course_id")))

    for w_col in WEEKLY_COLLECTIONS:
        pipeline = []
        if sample_size and sample_size > 0:
            pipeline.append({"$sample": {"size": sample_size}})
        pipeline.append({"$group": {"_id": {"pid": "$pid", "course_id": "$course_id"}}})

        weekly_pairs: Set[Tuple[str, str]] = set()
        async for doc in db[w_col].aggregate(pipeline):
            if doc.get("_id"):
                weekly_pairs.add((doc["_id"].get("pid"), doc["_id"].get("course_id")))

        orphan_pairs = weekly_pairs - enrolment_pairs
        if orphan_pairs:
            sample = list(orphan_pairs)[:3]
            violations.append(
                f"Check 3 Failed: Collection '{w_col}' contains {len(orphan_pairs)} (pid, course_id) pair(s) without enrolment! Sample: {sample}"
            )
        else:
            print(f"  [PASS] Check 3: All ({len(weekly_pairs)}) student-course pairs in '{w_col}' have active enrolments.")

    # ── Check 4: No PII fields in analytics & PIDs match Feature 5 format ─────
    pii_query = {
        "$or": [
            {"student_id": {"$exists": True}},
            {"registration_id": {"$exists": True}},
            {"name": {"$exists": True}},
            {"email": {"$exists": True}},
        ]
    }
    pid_pattern_regex = r"^STU_[0-9a-fA-F]{8}$"
    bad_pid_query = {
        "pid": {"$exists": True, "$not": {"$regex": pid_pattern_regex}}
    }

    for a_col in ANALYTICS_COLLECTIONS:
        # Check for forbidden identity fields
        pii_count = await db[a_col].count_documents(pii_query)
        if pii_count > 0:
            violations.append(
                f"Check 4 Failed: Analytics collection '{a_col}' contains {pii_count} document(s) with forbidden PII field(s)!"
            )

        # Check PID format
        bad_pid_count = await db[a_col].count_documents(bad_pid_query)
        if bad_pid_count > 0:
            violations.append(
                f"Check 4 Failed: Collection '{a_col}' contains {bad_pid_count} document(s) with invalid PID format (not STU_xxxxxxxx)!"
            )

    if not any("Check 4" in v for v in violations):
        print(f"  [PASS] Check 4: All {len(ANALYTICS_COLLECTIONS)} analytics collections are free of PII and use valid PIDs.")

    is_healthy = len(violations) == 0
    return is_healthy, violations


def main():
    parser = argparse.ArgumentParser(description="Database Integrity Verification Script.")
    parser.add_argument("--uri", type=str, default=None, help="Override MongoDB connection URI.")
    parser.add_argument("--db-name", type=str, default=None, help="Override database name.")
    parser.add_argument("--sample", type=int, default=None, help="Sample size for large datasets.")

    args = parser.parse_args()

    target_uri = args.uri or settings.mongo_uri
    target_db_name = args.db_name or settings.mongo_db_name
    client = create_mongo_client(target_uri)
    db = client[target_db_name]

    is_healthy, violations = asyncio.run(verify_integrity(db, sample_size=args.sample))
    client.close()

    print("\n════════════════════════════════════════════════════════════════")
    if is_healthy:
        print("[SUCCESS] All database referential integrity checks passed cleanly (0 violations).")
        sys.exit(0)
    else:
        print(f"[ERROR] Database integrity verification failed with {len(violations)} violation(s):")
        for v in violations:
            print(f"  * {v}")
        sys.exit(1)


if __name__ == "__main__":
    main()
