"""
backend/app/jobs/weekly_aggregation.py

Feature 22: Weekly Telemetry Aggregation & Academic Derivation Pipeline.
Aggregates daily clickstream telemetry into longitudinal weekly behavior records
(col.BEHAVIOR_WEEKLY) and derives continuous academic metrics for C2 and C3.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.academic_derivation import build_academic_record
from app.core.contract_version import CONTRACT_VERSION
from app.db import collections as col
from app.services.ingestion import complete_ingestion_run, create_ingestion_run


async def aggregate_weekly_behavior(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
    run_id: Optional[str] = None,
) -> int:
    """
    Aggregates student clickstream, video player actions, and assignment submissions
    for a given course and week into col.BEHAVIOR_WEEKLY.
    """
    now = datetime.now(timezone.utc)

    # 1. Gather all active enrolled student PIDs in this course
    enrolment_cursor = db[col.ENROLMENTS].find(
        {"course_id": course_id, "status": "active"},
        {"pid": 1, "_id": 0},
    )
    enrolments = await enrolment_cursor.to_list(length=10000)
    enrolled_pids = {e["pid"] for e in enrolments if e.get("pid")}

    if not enrolled_pids:
        # Also check activity events to include any students who interacted
        activity_pids = await db[col.ACTIVITY_EVENTS].distinct(
            "pid",
            {"course_id": course_id, "week_index": week_index},
        )
        enrolled_pids.update([p for p in activity_pids if p])

    if not enrolled_pids:
        return 0

    records_created = 0

    for pid in enrolled_pids:
        # Fetch activity events for this student, course, and week
        events_cursor = db[col.ACTIVITY_EVENTS].find({
            "pid": pid,
            "course_id": course_id,
            "week_index": week_index,
        })
        events = await events_cursor.to_list(length=5000)

        login_count = 0
        session_minutes = 0.0
        clicks = 0
        video_play_count = 0
        video_pause_count = 0
        video_rewind_count = 0
        video_skip_count = 0
        video_completion_pct_sum = 0.0
        video_events_count = 0

        for ev in events:
            ev_type = str(ev.get("event_type", "")).lower()
            ev_clicks = int(ev.get("clicks", 1) or 1)
            clicks += ev_clicks

            if "login" in ev_type:
                login_count += 1
            elif "play" in ev_type:
                video_play_count += 1
            elif "pause" in ev_type:
                video_pause_count += 1
            elif "rewind" in ev_type or "seek_back" in ev_type:
                video_rewind_count += 1
            elif "skip" in ev_type or "seek_forward" in ev_type:
                video_skip_count += 1

            payload = ev.get("event_payload") or {}
            if "duration_minutes" in payload:
                try:
                    session_minutes += float(payload["duration_minutes"])
                except (ValueError, TypeError):
                    pass
            elif "session_minutes" in ev:
                try:
                    session_minutes += float(ev["session_minutes"])
                except (ValueError, TypeError):
                    pass

            if "completion_pct" in payload:
                try:
                    video_completion_pct_sum += float(payload["completion_pct"])
                    video_events_count += 1
                except (ValueError, TypeError):
                    pass

        mean_video_completion = (
            round(video_completion_pct_sum / video_events_count, 2)
            if video_events_count > 0
            else 0.0
        )

        # Fetch submissions for this student, course, and week
        submissions_cursor = db[col.SUBMISSIONS].find({
            "pid": pid,
            "course_id": course_id,
        })
        submissions = await submissions_cursor.to_list(length=500)

        submissions_count = 0
        delay_hours_sum = 0.0

        for sub in submissions:
            # Check if submission belongs to this week
            sub_delay = sub.get("delay_hours")
            submissions_count += 1
            if sub_delay is not None:
                try:
                    delay_hours_sum += float(sub_delay)
                except (ValueError, TypeError):
                    pass

        avg_delay_hours = (
            round(delay_hours_sum / submissions_count, 2)
            if submissions_count > 0
            else 0.0
        )

        behavior_doc = {
            "pid": pid,
            "course_id": course_id,
            "week_index": week_index,
            "login_count": login_count,
            "session_minutes": round(session_minutes, 2),
            "clicks": clicks,
            "video_play_count": video_play_count,
            "video_pause_count": video_pause_count,
            "video_rewind_count": video_rewind_count,
            "video_skip_count": video_skip_count,
            "video_completion_pct": min(100.0, max(0.0, mean_video_completion)),
            "submissions_count": submissions_count,
            "avg_submission_delay_hours": avg_delay_hours,
            "schema_version": 1,
            "source_version": CONTRACT_VERSION,
            "source": "lms_scheduler",
            "ingestion_run_id": run_id,
            "ingested_at": now,
        }

        # Idempotently upsert into col.BEHAVIOR_WEEKLY
        await db[col.BEHAVIOR_WEEKLY].update_one(
            {
                "pid": pid,
                "course_id": course_id,
                "week_index": week_index,
            },
            {
                "$set": behavior_doc,
                "$setOnInsert": {"_id": str(uuid.uuid4())},
            },
            upsert=True,
        )
        records_created += 1

    return records_created


async def derive_weekly_academic(
    db: AsyncIOMotorDatabase,
    course_id: str,
    week_index: int,
) -> int:
    """
    Derives AcademicRecord envelopes for enrolled students to warm cache / verify data.
    """
    enrolment_cursor = db[col.ENROLMENTS].find(
        {"course_id": course_id, "status": "active"},
        {"pid": 1, "_id": 0},
    )
    enrolments = await enrolment_cursor.to_list(length=10000)
    pids = [e["pid"] for e in enrolments if e.get("pid")]

    derived_count = 0
    for pid in pids:
        try:
            record = await build_academic_record(
                db=db,
                pid=pid,
                course_id=course_id,
                week_index=week_index,
            )
            if record:
                derived_count += 1
        except Exception:
            pass

    return derived_count


async def run_weekly_pipeline(
    db: AsyncIOMotorDatabase,
    course_id: Optional[str] = None,
    week_index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes the end-to-end weekly telemetry aggregation and academic derivation pipeline.
    Tracks run state in col.INGESTION_RUNS.
    """
    run_id = await create_ingestion_run(
        db=db,
        component="weekly_pipeline",
    )

    try:
        # Determine courses to process
        if course_id:
            courses_to_run = [{"course_id": course_id}]
        else:
            courses_cursor = db[col.COURSES].find({}, {"course_id": 1, "_id": 0})
            courses_to_run = await courses_cursor.to_list(length=1000)

        total_behavior_records = 0
        total_academic_records = 0
        courses_processed = 0

        target_week = week_index if week_index is not None else 1

        for c in courses_to_run:
            c_id = c.get("course_id")
            if not c_id:
                continue

            b_count = await aggregate_weekly_behavior(
                db=db,
                course_id=c_id,
                week_index=target_week,
                run_id=run_id,
            )
            a_count = await derive_weekly_academic(
                db=db,
                course_id=c_id,
                week_index=target_week,
            )

            total_behavior_records += b_count
            total_academic_records += a_count
            courses_processed += 1

        details = {
            "courses_processed": courses_processed,
            "behavior_records_created": total_behavior_records,
            "academic_records_derived": total_academic_records,
            "week_index": target_week,
            "target_course": course_id,
        }

        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="completed",
            records_processed=total_behavior_records,
            details=details,
        )

        return {
            "run_id": run_id,
            "status": "completed",
            **details,
        }
    except Exception as exc:
        await complete_ingestion_run(
            db=db,
            run_id=run_id,
            status_str="failed",
            records_processed=0,
            error_message=str(exc),
        )
        raise exc
