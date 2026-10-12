#!/usr/bin/env python3
"""
scripts/import_oulad.py

Feature 26: OULAD Dataset Import & Rollback CLI Tool.
Usage:
  # Dry-run validation
  python scripts/import_oulad.py --dir /path/to/oulad --dry-run

  # Import sample of 100 students for modules AAA,BBB
  python scripts/import_oulad.py --dir /path/to/oulad --sample 100 --seed 42 --modules AAA,BBB --yes

  # Rollback all imported OULAD records
  python scripts/import_oulad.py --remove-source oulad --yes
"""

import argparse
import sys
from pathlib import Path

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

from app.core.config import settings
from app.importers.oulad.engine import OuladImportEngine


def confirm_prompt(prompt_text: str) -> bool:
    """Prompts user for interactive confirmation."""
    try:
        reply = input(f"{prompt_text} [y/N]: ").strip().lower()
        return reply in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Feature 26: Open University Learning Analytics Dataset (OULAD) Import & Rollback CLI."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to directory containing the 7 OULAD CSV files.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample N unique students deterministically using --seed.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic student sampling (default: 42).",
    )
    parser.add_argument(
        "--modules",
        type=str,
        default=None,
        help="Comma-separated module filter (e.g. 'AAA,BBB').",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Chunk size for reading studentVle.csv (default: 50,000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate schemas without persisting any records.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompts.",
    )
    parser.add_argument(
        "--remove-source",
        type=str,
        choices=["oulad"],
        default=None,
        help="Rollback mode: deletes all records with source='oulad' from target collections.",
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=None,
        help="Override MongoDB connection URI.",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help="Override target MongoDB database name.",
    )

    args = parser.parse_args()

    target_uri = args.uri or settings.mongo_uri
    target_db_name = args.db_name or settings.mongo_db_name
    is_test_db = "test" in target_db_name.lower()

    # ── Rollback Mode ─────────────────────────────────────────────────────────
    if args.remove_source:
        print(f"\n[ROLLBACK MODE] Request to delete all records with source='{args.remove_source}' from '{target_db_name}'.")
        if not args.yes:
            if not confirm_prompt("Proceed with deletion? (Audit logs and consent records will be preserved)"):
                print("Aborted by user.")
                sys.exit(0)

        engine = OuladImportEngine(
            data_dir=Path(args.dir or "."),
            mongo_uri=target_uri,
            db_name=target_db_name,
            dry_run=args.dry_run,
        )
        print("Executing rollback...")
        deleted_counts = engine.rollback()

        print("\n════════════════════════════════════════════════════════════════")
        print(" [ROLLBACK COMPLETE] Deleted Records Summary:")
        for col_name, count in sorted(deleted_counts.items()):
            print(f"   - {col_name:<24}: {count:>8} document(s) removed")
        print("════════════════════════════════════════════════════════════════\n")
        return

    # ── Import Mode ───────────────────────────────────────────────────────────
    if not args.dir:
        print("Error: --dir is required for import mode.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    data_path = Path(args.dir).resolve()
    if not data_path.exists() or not data_path.is_dir():
        print(f"Error: Specified --dir path does not exist or is not a directory: {data_path}", file=sys.stderr)
        sys.exit(1)

    # Interactive Confirmation for non-test databases
    if not is_test_db and not args.yes and not args.dry_run:
        prompt_msg = f"Target database '{target_db_name}' appears to be a production/shared database. Proceed with OULAD import?"
        if not confirm_prompt(prompt_msg):
            print("Aborted by user.")
            sys.exit(0)

    modules_list = [m.strip() for m in args.modules.split(",")] if args.modules else None

    print(f"\n[OULAD INGESTION INITIALIZING]")
    print(f"  Data Directory : {data_path}")
    print(f"  Target Database: {target_db_name}")
    print(f"  Chunk Size     : {args.chunk_size:,}")
    print(f"  Sample Limit   : {args.sample if args.sample else 'Full Dataset'}")
    print(f"  Random Seed    : {args.seed}")
    print(f"  Module Filter  : {modules_list or 'All Modules'}")
    print(f"  Dry Run        : {args.dry_run}\n")

    engine = OuladImportEngine(
        data_dir=data_path,
        mongo_uri=target_uri,
        db_name=target_db_name,
        chunk_size=args.chunk_size,
        sample_size=args.sample,
        seed=args.seed,
        modules=modules_list,
        dry_run=args.dry_run,
    )

    try:
        stats = engine.run_import()

        print("\n════════════════════════════════════════════════════════════════")
        if args.dry_run:
            print(" [DRY RUN COMPLETE] Zero database writes performed.")
        else:
            print(f" [IMPORT COMPLETE] Run ID: {stats['run_id']}")
        print(f" Duration: {stats['duration_seconds']}s")
        print(f" Total Processed: {stats['total_records_processed']:,} document(s)\n")
        print(" Collections Written:")
        for col_name, count in sorted(stats["collections_written"].items()):
            print(f"   - {col_name:<24}: {count:>8,}")

        if stats["records_skipped_duplicate"] > 0:
            print(f"\n Skipped Duplicates: {stats['records_skipped_duplicate']:,} (already loaded)")
        if stats["records_beyond_course_length"] > 0:
            print(f" Records Beyond Course Length: {stats['records_beyond_course_length']:,} (clamped to max week)")

        if stats["rejected_records"]:
            print("\n [WARNING] Validation Rejections (not imported):")
            for reason, r_count in stats["rejected_records"].items():
                print(f"   - {reason}: {r_count} row(s)")
        else:
            print("\n Validation Status: 100% of parsed records passed Pydantic and $jsonSchema validation.")
        print("════════════════════════════════════════════════════════════════\n")

    except Exception as exc:
        print(f"\n[FATAL ERROR] Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
