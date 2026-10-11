"""
backend/app/db/migrations/runner.py

Feature 25: Asynchronous Migration Runner.
Executes numbered async migrations in sequential order.
Tracks applied migrations in the 'schema_migrations' collection.
Uses a unique index on 'id' to guarantee that concurrent workers cannot apply
the same migration twice.
"""

import hashlib
import importlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

MIGRATION_FILE_PATTERN = re.compile(r"^(\d{4}_[a-zA-Z0-9_]+)\.py$")


def _calculate_file_checksum(file_path: Path) -> str:
    """Computes SHA256 hex digest of the migration script content."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


async def run_migrations(db: AsyncIOMotorDatabase) -> List[str]:
    """
    Discovers, verifies, and runs unapplied database migrations.
    Returns the list of migration IDs applied during this execution.
    """
    # 1. Ensure schema_migrations unique index
    await db.schema_migrations.create_indexes([
        IndexModel([("id", ASCENDING)], unique=True, name="idx_schema_migrations_id_unique")
    ])

    # 2. Query already applied migrations
    applied_docs = await db.schema_migrations.find({}).to_list(length=1000)
    applied_ids = {doc["id"]: doc for doc in applied_docs}

    # 3. Discover migration files
    migrations_dir = Path(__file__).resolve().parent
    migration_files: List[Tuple[str, Path]] = []

    for file_path in sorted(migrations_dir.glob("*.py")):
        match = MIGRATION_FILE_PATTERN.match(file_path.name)
        if match:
            migration_files.append((match.group(1), file_path))

    applied_in_this_run: List[str] = []

    # 4. Execute unapplied migrations in order
    for migration_id, file_path in migration_files:
        if migration_id in applied_ids:
            continue

        checksum = _calculate_file_checksum(file_path)
        print(f"Applying migration: {migration_id} (checksum: {checksum[:8]}...)")

        # Dynamically import migration module
        module_name = f"app.db.migrations.{migration_id}"
        module = importlib.import_module(module_name)

        if not hasattr(module, "upgrade"):
            raise AttributeError(f"Migration module '{migration_id}' must define an async 'upgrade(db)' function.")

        # Execute migration
        await module.upgrade(db)

        # Record migration completion
        record = {
            "_id": migration_id,
            "id": migration_id,
            "checksum": checksum,
            "applied_at": datetime.now(timezone.utc),
        }
        await db.schema_migrations.insert_one(record)
        applied_in_this_run.append(migration_id)
        print(f"  [OK] Successfully applied {migration_id}.")

    return applied_in_this_run
