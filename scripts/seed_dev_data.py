#!/usr/bin/env python3
"""
scripts/seed_dev_data.py

Feature 25: Development Seed Data Generator.
Populates a small, consistent development dataset:
- 10 pseudonymized students (PIDs generated via Feature 5 HMAC)
- 2 Courses (CS101, SE4020) with 6 course weeks each
- Enrolments linking students to courses
- Longitudinal weekly analytics (weeks 0 - 5) across behavior_weekly,
  affective_weekly, engagement_trajectories, risk_assessments, grades, attendance
- Recommendations and intervention outcomes built from Feature 24 fixtures

Invariants:
- Uses PIDs only in analytics collections; never real identities.
- Completely idempotent: uses update_one(..., upsert=True).
- Safe to run repeatedly.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

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
from app.core.privacy import pseudonymize
from app.db import collections as col
from tests.fixtures.contract import (
    VALID_AFFECTIVE_VECTOR_ENVELOPE,
    VALID_BEHAVIOR_WEEKLY_ENVELOPE,
    VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE,
    VALID_INTERVENTION_OUTCOME_ENVELOPE,
    VALID_INTERVENTION_REC_ENVELOPE,
    VALID_RISK_ASSESSMENT_ENVELOPE,
    VALID_TEXT_MESSAGE_ENVELOPE,
)


async def seed_data(db: AsyncIOMotorDatabase) -> None:
    """Populates development dataset using idempotent upserts."""
    print(f"Seeding development dataset into '{db.name}'...")
    base_time = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

    # ── 1. Create 10 Students in Identity Vault ───────────────────────────────
    students: List[Dict[str, str]] = []
    for i in range(1, 11):
        raw_student_id = f"IT2026{i:04d}"
        pid = pseudonymize(raw_student_id)
        name = f"Test Student {i}"
        email = f"student{i}@lms.edu"
        students.append({"pid": pid, "student_id": raw_student_id, "name": name, "email": email})

        # Upsert into identity_vault
        vault_doc = {
            "_id": pid,
            "pid": pid,
            "student_id": raw_student_id,
            "name": name,
            "email": email,
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
        }
        await db[col.IDENTITY_VAULT].update_one({"_id": pid}, {"$set": vault_doc}, upsert=True)

    print(f"  [+] Seeded {len(students)} pseudonymized students in identity_vault.")

    # ── 2. Create 2 Courses & Course Weeks ─────────────────────────────────────
    courses = [
        {"course_id": "CS101", "title": "Introduction to Computer Systems", "description": "Core computing fundamentals"},
        {"course_id": "SE4020", "title": "Advanced Software Engineering", "description": "System architecture and MLops"},
    ]

    for c in courses:
        cid = c["course_id"]
        course_doc = {
            "_id": cid,
            "course_id": cid,
            "title": c["title"],
            "description": c["description"],
            "is_published": True,
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
            "created_at": base_time,
            "updated_at": base_time,
        }
        await db[col.COURSES].update_one({"_id": cid}, {"$set": course_doc}, upsert=True)

        # Create 6 course weeks (weeks 0 to 5)
        for w in range(6):
            week_id = f"{cid}_W{w}"
            start = base_time + timedelta(days=w * 7)
            end = start + timedelta(days=7)
            week_doc = {
                "_id": week_id,
                "course_id": cid,
                "week_index": w,
                "title": f"Week {w + 1}",
                "start_date": start,
                "end_date": end,
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
            }
            await db[col.COURSE_WEEKS].update_one({"_id": week_id}, {"$set": week_doc}, upsert=True)

    print("  [+] Seeded 2 courses and 12 course weeks.")

    # ── 3. Create Enrolments ───────────────────────────────────────────────────
    for s in students:
        for c in courses:
            enrolment_id = f"{s['pid']}_{c['course_id']}"
            enrol_doc = {
                "_id": enrolment_id,
                "pid": s["pid"],
                "course_id": c["course_id"],
                "enrolment_start": base_time,
                "status": "active",
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
            }
            await db[col.ENROLMENTS].update_one({"_id": enrolment_id}, {"$set": enrol_doc}, upsert=True)

    print(f"  [+] Seeded {len(students) * len(courses)} student enrolments.")

    # ── 4. Weekly Analytics & Interactions (Weeks 0 - 5) ──────────────────────
    # Base payloads from Feature 24 fixtures
    aff_base = VALID_AFFECTIVE_VECTOR_ENVELOPE["data"]
    beh_base = VALID_BEHAVIOR_WEEKLY_ENVELOPE["data"]
    eng_base = VALID_ENGAGEMENT_TRAJECTORY_ENVELOPE["data"]
    risk_base = VALID_RISK_ASSESSMENT_ENVELOPE["data"]
    msg_base = VALID_TEXT_MESSAGE_ENVELOPE["data"]

    record_count = 0
    for s in students:
        pid = s["pid"]
        for c in courses:
            cid = c["course_id"]
            for w in range(6):
                key = f"{pid}_{cid}_{w}"
                ts = base_time + timedelta(days=w * 7 + 3)

                # 1. Behavior weekly
                beh_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "login_count": beh_base["login_count"] + (w % 3),
                    "session_minutes": beh_base["session_minutes"] + (w * 10.0),
                    "clicks": beh_base["clicks"] + (w * 25),
                    "video_play_count": beh_base["video_play_count"],
                    "video_pause_count": beh_base["video_pause_count"],
                    "video_rewind_count": beh_base["video_rewind_count"],
                    "video_skip_count": beh_base["video_skip_count"],
                    "video_completion_pct": min(100.0, beh_base["video_completion_pct"] - (w * 2.0)),
                    "submissions_count": beh_base["submissions_count"],
                    "avg_submission_delay_hours": beh_base["avg_submission_delay_hours"],
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.BEHAVIOR_WEEKLY].update_one({"_id": key}, {"$set": beh_doc}, upsert=True)

                # 2. Affective weekly
                aff_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "emotion_scores": aff_base["emotion_scores"],
                    "stress_label": aff_base["stress_label"],
                    "confidence": aff_base["confidence"],
                    "message_count": aff_base["message_count"],
                    "top_drivers": aff_base["top_drivers"],
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.AFFECTIVE_WEEKLY].update_one({"_id": key}, {"$set": aff_doc}, upsert=True)

                # 3. Engagement trajectory
                eng_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "trajectory_label": eng_base["trajectory_label"],
                    "confidence": eng_base["confidence"],
                    "contributing_indicators": eng_base["contributing_indicators"],
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.ENGAGEMENT_TRAJECTORIES].update_one({"_id": key}, {"$set": eng_doc}, upsert=True)

                # 4. Risk assessment
                risk_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "risk_score": risk_base["risk_score"],
                    "risk_tier": risk_base["risk_tier"],
                    "modality_contributions": risk_base["modality_contributions"],
                    "top_drivers": risk_base["top_drivers"],
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.RISK_ASSESSMENTS].update_one({"_id": key}, {"$set": risk_doc}, upsert=True)

                # 5. Grades
                grade_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "grade_item": f"Quiz {w + 1}",
                    "score": 82.5,
                    "max_score": 100.0,
                    "weight_pct": 10.0,
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.GRADES].update_one({"_id": key}, {"$set": grade_doc}, upsert=True)

                # 6. Attendance
                att_doc = {
                    "_id": key,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "sessions_scheduled": 2,
                    "sessions_attended": 2,
                    "attendance_pct": 100.0,
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.ATTENDANCE].update_one({"_id": key}, {"$set": att_doc}, upsert=True)

                # 7. Messages (one message per student per week)
                msg_id = f"msg_{key}"
                msg_doc = {
                    "_id": msg_id,
                    "message_id": msg_id,
                    "pid": pid,
                    "course_id": cid,
                    "week_index": w,
                    "source_type": "forum",
                    "clean_text": f"Weekly reflection query for week {w + 1} regarding algorithmic complexity.",
                    "timestamp": ts,
                    "response_latency_seconds": 150.0,
                    "message_length_chars": 72,
                    "message_length_words": 9,
                    "reply_to_id": None,
                    "schema_version": 1,
                    "ingested_at": ts,
                    "source_version": "1.0",
                }
                await db[col.MESSAGES].update_one({"_id": msg_id}, {"$set": msg_doc}, upsert=True)

                record_count += 1

    print(f"  [+] Seeded {record_count * 7} weekly analytics & communication records across 6 weeks.")

    # ── 5. Seed Recommendations & Outcomes ────────────────────────────────────
    rec_base = VALID_INTERVENTION_REC_ENVELOPE["data"]
    out_base = VALID_INTERVENTION_OUTCOME_ENVELOPE["data"]

    for i, s in enumerate(students[:4]):
        rec_id = f"rec_seed_{i + 1}"
        rec_doc = {
            "_id": rec_id,
            "recommendation_id": rec_id,
            "pid": s["pid"],
            "week_index": 3,
            "candidates": rec_base["candidates"],
            "status": "proposed",
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
        }
        await db[col.RECOMMENDATIONS].update_one({"_id": rec_id}, {"$set": rec_doc}, upsert=True)

        out_doc = {
            "_id": rec_id,
            "recommendation_id": rec_id,
            "decision": "approved",
            "completed": True,
            "observed_change": out_base["observed_change"],
            "notes_present": True,
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
        }
        await db[col.INTERVENTION_OUTCOMES].update_one({"_id": rec_id}, {"$set": out_doc}, upsert=True)

    print("  [+] Seeded sample recommendations and intervention outcomes.")
    print("[SUCCESS] Development data seeded successfully (zero PII in analytics).")


def main():
    parser = argparse.ArgumentParser(description="Seed development dataset.")
    parser.add_argument("--uri", type=str, default=None, help="Override MongoDB URI.")
    parser.add_argument("--db-name", type=str, default=None, help="Override database name.")

    args = parser.parse_args()
    target_uri = args.uri or settings.mongo_uri
    target_db_name = args.db_name or settings.mongo_db_name

    client = create_mongo_client(target_uri)
    db = client[target_db_name]

    asyncio.run(seed_data(db))
    client.close()


if __name__ == "__main__":
    main()
