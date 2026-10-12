#!/usr/bin/env python3
"""
scripts/run_pipeline_tick.py

CLI runner for Feature 22: Weekly scheduler / pipeline orchestrator.
Executes an orchestrator tick:
- Discovers finished course weeks past grace period
- Creates pipeline runs idempotently
- Progresses stages and dispatches notifications
- Supports --dry-run, --now override, --include-sources, and --course-id
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Setup sys.path for host and Docker container execution
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
from app.core.database import create_mongo_client
from app.pipeline.orchestrator import run_pipeline_tick

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.run_pipeline_tick")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Feature 22 Weekly Pipeline Tick",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate tick without persisting runs or stage updates to MongoDB",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="ISO 8601 timestamp override for deterministic replay (e.g. 2026-10-15T00:00:00Z)",
    )
    parser.add_argument(
        "--include-sources",
        type=str,
        default=None,
        help="Comma-separated list of course sources to include (e.g. oulad,demo)",
    )
    parser.add_argument(
        "--course-id",
        type=str,
        default=None,
        help="Filter tick execution to a single course ID",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    now_dt: Optional[datetime] = None
    if args.now:
        try:
            now_dt = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            logger.error("Invalid --now timestamp: %s", exc)
            return 1

    include_sources: Optional[List[str]] = None
    if args.include_sources:
        include_sources = [s.strip().lower() for s in args.include_sources.split(",") if s.strip()]

    client = create_mongo_client(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    try:
        report = await run_pipeline_tick(
            db=db,
            now=now_dt,
            dry_run=args.dry_run,
            include_sources=include_sources,
            target_course_id=args.course_id,
        )

        print("\n" + "=" * 60)
        print("PIPELINE TICK EXECUTION REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2))
        print("=" * 60 + "\n")

        if report.get("status") == "skipped":
            logger.info("Tick was skipped: %s", report.get("reason"))
            return 0

        logger.info(
            "Tick completed successfully: %d created, %d advanced.",
            report.get("runs_created", 0),
            report.get("runs_advanced", 0),
        )
        return 0

    except Exception as exc:
        logger.exception("Pipeline tick execution failed: %s", exc)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
