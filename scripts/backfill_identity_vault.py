#!/usr/bin/env python3
"""
scripts/backfill_identity_vault.py

Backfills missing identity_vault records for users with role == "student".
Rules:
  - Preserves existing user PID (never recomputes it).
  - Creates the vault entry using user's pid, full_name, and email.
  - If no real student_id is known, uses placeholder UNKNOWN-<pid>.
  - Sets source: "backfill" and is_imported: False.
  - Skips users that already have a vault entry.
  - Supports --dry-run and optional --email filter.
  - Idempotent and safe to run multiple times.
  - Privacy guarantee: Prints counts only (created, already existed, skipped).
    Never prints names, emails, or credentials.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

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
from app.db import collections as col


async def backfill_identity_vault(
    db: AsyncIOMotorDatabase,
    dry_run: bool = False,
    email_filter: Optional[str] = None,
) -> Dict[str, int]:
    """
    Backfills missing identity_vault records for student accounts.
    Returns summary counts: {'created': X, 'already_existed': Y, 'skipped': Z}.
    """
    query: Dict = {"role": "student"}
    if email_filter and email_filter.strip():
        query["email"] = email_filter.strip().lower()

    users_cursor = db[col.USERS].find(query)
    users = await users_cursor.to_list(length=100000)

    counts: Dict[str, int] = {
        "created": 0,
        "already_existed": 0,
        "skipped": 0,
    }

    now = datetime.now(timezone.utc)

    for user in users:
        pid = user.get("pid")
        if not pid or not isinstance(pid, str) or not pid.strip():
            counts["skipped"] += 1
            continue

        pid = pid.strip()

        # Check if vault record already exists for this PID
        existing_vault = await db[col.IDENTITY_VAULT].find_one({"_id": pid})
        if not existing_vault:
            existing_vault = await db[col.IDENTITY_VAULT].find_one({"pid": pid})

        if existing_vault:
            counts["already_existed"] += 1
            continue

        # Extract or construct student_id
        student_id = (
            user.get("student_id")
            or (user.get("profile") or {}).get("student_id")
            or f"UNKNOWN-{pid}"
        )

        name = user.get("full_name") or "Student"
        email = user.get("email") or f"{pid.lower()}@lms.local"

        vault_doc = {
            "_id": pid,
            "pid": pid,
            "student_id": str(student_id).strip(),
            "name": str(name).strip(),
            "email": str(email).strip(),
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
            "is_imported": False,
            "source": "backfill",
            "created_at": now,
            "updated_at": now,
        }

        if not dry_run:
            await db[col.IDENTITY_VAULT].update_one(
                {"_id": pid},
                {"$setOnInsert": vault_doc},
                upsert=True,
            )

        counts["created"] += 1

    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing identity_vault entries for students."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts without writing to the database.",
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Optional filter to backfill for a single user by email.",
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=None,
        help="Optional MongoDB connection string override.",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help="Optional database name override.",
    )

    args = parser.parse_args()

    client = create_mongo_client(args.uri)
    db_name = args.db_name or settings.mongo_db_name
    db = client[db_name]

    try:
        counts = await backfill_identity_vault(
            db=db,
            dry_run=args.dry_run,
            email_filter=args.email,
        )
        mode_label = "[DRY-RUN] " if args.dry_run else ""
        print(f"{mode_label}Identity Vault Backfill Summary:")
        print(f"  created: {counts['created']}")
        print(f"  already_existed: {counts['already_existed']}")
        print(f"  skipped: {counts['skipped']}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
