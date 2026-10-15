#!/usr/bin/env python3
"""
scripts/setup_db.py

Feature 25: Idempotent MongoDB Database Setup Script.
Applies:
- Strict $jsonSchema validators (or moderate if existing data fails compatibility scan)
- validationLevel ('strict' for new, 'moderate' if downgraded) and validationAction ('error')
- Idempotent collection creation and collMod updates
- Indexes defined in app.db.indexes (preserves existing indexes)
- CLI Flags:
    --dry-run : Preview changes without applying
    --check   : Exit with status 1 if database definitions drift (CI check)
    --uri     : Override MongoDB connection string
    --db-name : Override database name (supports throwaway test DBs)
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

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

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import create_mongo_client
from app.db.collections import ALL_COLLECTIONS, EXISTING_COLLECTIONS
from app.db.indexes import COLLECTION_INDEXES
from app.db.validators import COLLECTION_VALIDATORS


async def scan_existing_compatibility(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    validator: Dict[str, Any],
) -> Tuple[bool, int, int]:
    """
    Performs a read-only compatibility scan of documents in collection_name
    against the candidate validator.
    Returns (is_compatible, failing_count, total_count).
    """
    total = await db[collection_name].count_documents({})
    if total == 0:
        return True, 0, 0

    valid_count = await db[collection_name].count_documents(validator)
    failing = total - valid_count
    return (failing == 0), failing, total


async def inspect_database_state(
    db: AsyncIOMotorDatabase,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Set[str]]]:
    """
    Retrieves current collection configurations and existing index names.
    Returns (collection_options, collection_indexes).
    """
    col_info = await db.command("listCollections")
    existing_cols = {c["name"]: c.get("options", {}) for c in col_info["cursor"]["firstBatch"]}

    existing_indexes: Dict[str, Set[str]] = {}
    for name in existing_cols:
        try:
            indexes = await db[name].index_information()
            existing_indexes[name] = set(indexes.keys())
        except Exception:
            existing_indexes[name] = set()

    return existing_cols, existing_indexes


async def setup_database(
    uri: str | None = None,
    db_name: str | None = None,
    dry_run: bool = False,
    check_only: bool = False,
) -> bool:
    """
    Idempotent database setup logic.
    Returns True if database matches target state (or was updated to match),
    Returns False if drift was detected in check_only mode.
    """
    target_uri = uri or settings.mongo_uri
    target_db_name = db_name or settings.mongo_db_name
    client = create_mongo_client(target_uri)
    db = client[target_db_name]

    print(f"Connecting to MongoDB database: '{target_db_name}'...")
    try:
        await db.command("ping")
    except Exception as exc:
        print(f"Error connecting to MongoDB: {exc}")
        client.close()
        return False

    existing_cols, existing_indexes = await inspect_database_state(db)
    changes_needed: List[str] = []
    downgraded_collections: List[str] = []

    # ── 1. Evaluate Collections & Validators ──────────────────────────────────
    for col_name in ALL_COLLECTIONS:
        validator = COLLECTION_VALIDATORS.get(col_name)
        if not validator:
            continue

        target_level = "strict"
        target_action = "error"

        if col_name not in existing_cols:
            changes_needed.append(f"CREATE collection '{col_name}' (strict)")
            if not dry_run and not check_only:
                await db.create_collection(
                    col_name,
                    validator=validator,
                    validationLevel=target_level,
                    validationAction=target_action,
                )
                print(f"  [+] Created collection '{col_name}' with strict validator.")
        else:
            # Collection already exists -> Check compatibility scan if in EXISTING_COLLECTIONS
            if col_name in EXISTING_COLLECTIONS:
                compatible, failing, total = await scan_existing_compatibility(db, col_name, validator)
                if not compatible:
                    target_level = "moderate"
                    downgraded_collections.append(f"{col_name} ({failing}/{total} docs incompatible -> moderate)")

            current_opts = existing_cols[col_name]
            cur_validator = current_opts.get("validator")
            cur_level = current_opts.get("validationLevel", "off")
            cur_action = current_opts.get("validationAction", "warn")

            needs_update = (
                cur_validator != validator or
                cur_level != target_level or
                cur_action != target_action
            )

            if needs_update:
                changes_needed.append(f"UPDATE validator '{col_name}' (level={target_level})")
                if not dry_run and not check_only:
                    await db.command(
                        "collMod",
                        col_name,
                        validator=validator,
                        validationLevel=target_level,
                        validationAction=target_action,
                    )
                    print(f"  [*] Updated validator for '{col_name}' (validationLevel={target_level}).")

    # ── 2. Evaluate Indexes ───────────────────────────────────────────────────
    for col_name, expected_models in COLLECTION_INDEXES.items():
        curr_idx_names = existing_indexes.get(col_name, set())

        indexes_to_create = []
        for model in expected_models:
            name = model.document.get("name")
            if not name:
                keys = model.document.get("key", [])
                name = "_".join(f"{k}_{v}" for k, v in keys.items())

            if name not in curr_idx_names:
                indexes_to_create.append(model)
                changes_needed.append(f"CREATE index '{name}' on '{col_name}'")

        if indexes_to_create and not dry_run and not check_only:
            try:
                await db[col_name].create_indexes(indexes_to_create)
                print(f"  [+] Created {len(indexes_to_create)} index(es) on '{col_name}'.")
            except Exception as exc:
                print(f"  [!] Warning creating indexes on '{col_name}': {exc}")

    client.close()

    # ── Report Results ────────────────────────────────────────────────────────
    if downgraded_collections:
        print("\n[Compatibility Notice] The following collections were downgraded to 'moderate' validation:")
        for down in downgraded_collections:
            print(f"  - {down}")

    if changes_needed:
        print(f"\n[Changes Detected: {len(changes_needed)} item(s)]")
        for ch in changes_needed:
            print(f"  * {ch}")
        if check_only:
            print("\n[CHECK FAILED] Database differs from defined schema and index specifications.")
            return False
        if dry_run:
            print("\n[DRY RUN COMPLETE] No modifications were applied.")
            return True
        print("\n[SETUP COMPLETE] Database updated successfully.")
        return True
    else:
        print("\n[OK] Database is up to date with all collections, validators, and indexes. Zero changes needed.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Idempotent MongoDB Schema and Index Setup Script.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying database.")
    parser.add_argument("--check", action="store_true", help="Check for schema drift (exit 1 if differing).")
    parser.add_argument("--uri", type=str, default=None, help="Override MongoDB connection URI.")
    parser.add_argument("--db-name", type=str, default=None, help="Override database name.")

    args = parser.parse_args()

    success = asyncio.run(setup_database(
        uri=args.uri,
        db_name=args.db_name,
        dry_run=args.dry_run,
        check_only=args.check,
    ))

    if not success and args.check:
        sys.exit(1)


if __name__ == "__main__":
    main()
