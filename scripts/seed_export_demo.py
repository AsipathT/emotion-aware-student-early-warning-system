#!/usr/bin/env python3
"""
scripts/seed_export_demo.py

Feature 21: Component Export Demo Dataset Generator.
Populates a small, consistent, pseudonymized development dataset for testing
Component 1, Component 2, and Component 3 data exports.

Dataset composition:
  - 6 students (PIDs only, never real identities)
  - 2 courses (DEMO101, DEMO202) across 4 weeks (weeks 0 to 3)
  - Consent distribution:
      * 3 students with ACCEPTED consent for active notice
      * 1 student with DECLINED consent
      * 1 student with WITHDRAWN consent
      * 1 student with NO consent record
  - Telemetry:
      * Messages (clean_text only, discussion & reflective journals)
      * Behavior weekly records (sessions, clicks, video player metrics)
      * Grades (continuous assessments with weights)
      * Attendance records
      * Assignments & Submissions (with delay hours)
      * Quizzes & Quiz attempts
      * A subset of records tagged with source='oulad' (research exempt)
  - All non-OULAD records are tagged with source='demo'
  - Completely idempotent (uses upsert).
  - Supports '--remove' flag to cleanly erase demo data.
"""

import argparse
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# Setup import path
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


DEMO_COLLECTIONS = [
    col.MESSAGES,
    col.BEHAVIOR_WEEKLY,
    col.GRADES,
    col.ATTENDANCE,
    col.SUBMISSIONS,
    col.ASSIGNMENTS,
    col.QUIZ_ATTEMPTS,
    col.QUIZZES,
    col.ENROLMENTS,
    col.COURSE_WEEKS,
    col.COURSES,
    col.CONSENT_RECORDS,
]


def generate_pid(index: int) -> str:
    """Generates deterministic Feature 5 compliant PID."""
    digest = hashlib.sha256(f"demo_export_student_ident_{index}".encode("utf-8")).hexdigest()
    return f"STU_{digest[:8]}"


def remove_demo_data(db) -> None:
    """Deletes all documents tagged with source='demo'."""
    print(f"Removing demo dataset from database '{db.name}'...")
    total_deleted = 0
    for collection_name in DEMO_COLLECTIONS:
        res = db[collection_name].delete_many({"source": "demo"})
        if res.deleted_count > 0:
            print(f"  [-] Deleted {res.deleted_count} demo doc(s) from '{collection_name}'.")
            total_deleted += res.deleted_count
    print(f"[CLEANUP COMPLETE] Total demo records deleted: {total_deleted}")


def seed_demo_data(db) -> None:
    """Inserts or updates the demo dataset."""
    print(f"Seeding demo export dataset into database '{db.name}'...")
    base_time = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

    # ── 1. Ensure Active Consent Notice Exists ─────────────────────────────────
    active_notice = db[col.CONSENT_NOTICES].find_one({"is_active": True})
    if not active_notice:
        active_notice_doc = {
            "_id": "notice_demo_v1",
            "id": "notice_demo_v1",
            "version": 1,
            "text": "Ethics and data privacy consent notice for analytics and research.",
            "effective_from": base_time,
            "is_active": True,
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
            "source": "demo",
        }
        db[col.CONSENT_NOTICES].update_one({"_id": "notice_demo_v1"}, {"$set": active_notice_doc}, upsert=True)
        active_version = 1
    else:
        active_version = active_notice.get("version", 1)

    # ── 2. 6 Students and Consent Distribution ────────────────────────────────
    # Students 1, 2, 3: Accepted
    # Student 4: Declined
    # Student 5: Withdrawn (Accepted first, then Withdrawn)
    # Student 6: No record
    students = [generate_pid(i) for i in range(1, 7)]

    # Student 1, 2, 3: Accepted
    for s_pid in students[:3]:
        doc = {
            "_id": f"consent_{s_pid}_v{active_version}",
            "pid": s_pid,
            "notice_version": active_version,
            "decision": "accepted",
            "timestamp": base_time + timedelta(hours=1),
            "ip_or_client": "127.0.0.1 | demo-client",
            "source": "demo",
        }
        db[col.CONSENT_RECORDS].update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)

    # Student 4: Declined
    doc_declined = {
        "_id": f"consent_{students[3]}_v{active_version}",
        "pid": students[3],
        "notice_version": active_version,
        "decision": "declined",
        "timestamp": base_time + timedelta(hours=2),
        "ip_or_client": "127.0.0.1 | demo-client",
        "source": "demo",
    }
    db[col.CONSENT_RECORDS].update_one({"_id": doc_declined["_id"]}, {"$set": doc_declined}, upsert=True)

    # Student 5: Accepted then Withdrawn
    doc_initial = {
        "_id": f"consent_{students[4]}_v{active_version}_initial",
        "pid": students[4],
        "notice_version": active_version,
        "decision": "accepted",
        "timestamp": base_time + timedelta(hours=1),
        "ip_or_client": "127.0.0.1 | demo-client",
        "source": "demo",
    }
    db[col.CONSENT_RECORDS].update_one({"_id": doc_initial["_id"]}, {"$set": doc_initial}, upsert=True)

    doc_withdrawn = {
        "_id": f"consent_{students[4]}_v{active_version}_final",
        "pid": students[4],
        "notice_version": active_version,
        "decision": "withdrawn",
        "timestamp": base_time + timedelta(hours=4),
        "ip_or_client": "127.0.0.1 | demo-client",
        "source": "demo",
    }
    db[col.CONSENT_RECORDS].update_one({"_id": doc_withdrawn["_id"]}, {"$set": doc_withdrawn}, upsert=True)

    print(f"  [+] Seeded consent records for 6 students (3 accepted, 1 declined, 1 withdrawn, 1 no-record).")

    # ── 3. Courses & Course Weeks ─────────────────────────────────────────────
    courses = ["DEMO101", "DEMO202"]
    for c_id in courses:
        c_doc = {
            "_id": c_id,
            "id": c_id,
            "course_id": c_id,
            "title": f"Demo Course {c_id}",
            "description": f"Test syllabus for {c_id}",
            "lecturer_id": "dummy-lecturer-demo",
            "is_published": True,
            "modules": [],
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
            "created_at": base_time,
            "updated_at": base_time,
            "source": "demo",
        }
        db[col.COURSES].update_one({"_id": c_id}, {"$set": c_doc}, upsert=True)

        for w in range(4):
            w_id = f"{c_id}_W{w}"
            w_doc = {
                "_id": w_id,
                "course_id": c_id,
                "week_index": w,
                "title": f"Week {w + 1}",
                "start_date": base_time + timedelta(days=w * 7),
                "end_date": base_time + timedelta(days=(w + 1) * 7),
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
                "source": "demo",
            }
            db[col.COURSE_WEEKS].update_one({"_id": w_id}, {"$set": w_doc}, upsert=True)

    print(f"  [+] Seeded 2 courses and 8 course weeks.")

    # ── 4. Enrolments ─────────────────────────────────────────────────────────
    for s_pid in students:
        for c_id in courses:
            enr_id = f"{s_pid}_{c_id}"
            enr_doc = {
                "_id": enr_id,
                "pid": s_pid,
                "course_id": c_id,
                "enrolment_start": base_time,
                "status": "active",
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
                "source": "demo",
            }
            db[col.ENROLMENTS].update_one({"_id": enr_id}, {"$set": enr_doc}, upsert=True)

    # ── 5. Assignments & Quizzes Metadata ─────────────────────────────────────
    assignments = []
    quizzes = []
    for c_id in courses:
        for w in range(4):
            asg_id = f"{c_id}_ASG_W{w}"
            assignments.append({
                "assignment_id": asg_id,
                "course_id": c_id,
                "week_index": w,
                "title": f"Assignment {w + 1}",
                "max_points": 100.0,
                "assessment_type": "TMA" if w % 2 == 0 else "CMA",
                "weight": 25.0,
            })
            qz_id = f"{c_id}_QZ_W{w}"
            quizzes.append({
                "quiz_id": qz_id,
                "course_id": c_id,
                "week_index": w,
                "title": f"Quiz {w + 1}",
                "max_score": 20.0,
            })

    for a in assignments:
        a_doc = dict(a)
        a_doc.update({
            "_id": a["assignment_id"],
            "due_date": base_time + timedelta(days=a["week_index"] * 7 + 5),
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
            "source": "demo",
        })
        db[col.ASSIGNMENTS].update_one({"_id": a["assignment_id"]}, {"$set": a_doc}, upsert=True)

    for q in quizzes:
        q_doc = dict(q)
        q_doc.update({
            "_id": q["quiz_id"],
            "schema_version": 1,
            "ingested_at": base_time,
            "source_version": "1.0",
            "source": "demo",
        })
        db[col.QUIZZES].update_one({"_id": q["quiz_id"]}, {"$set": q_doc}, upsert=True)

    # ── 6. Weekly Records across 4 weeks ──────────────────────────────────────
    msg_count = 0
    beh_count = 0
    sample_texts = [
        "The lecture examples for algorithmic sorting were very clear and practical.",
        "Could someone explain how Dijkstra handles negative weights?",
        "Completed the practice questions and feel confident for the upcoming assessment.",
        "Working on the week's programming task; debugging tree traversal logic.",
    ]

    for s_idx, s_pid in enumerate(students):
        for c_id in courses:
            for w in range(4):
                time_w = base_time + timedelta(days=w * 7 + 2)

                # Messages
                m_id = f"MSG_{s_pid}_{c_id}_W{w}"
                clean_msg = sample_texts[(w + s_idx) % len(sample_texts)]
                m_doc = {
                    "_id": m_id,
                    "message_id": m_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "week_index": w,
                    "source_type": "forum" if w % 2 == 0 else "journal",
                    "clean_text": clean_msg,
                    "timestamp": time_w,
                    "response_latency_seconds": 120.0,
                    "message_length_chars": len(clean_msg),
                    "message_length_words": len(clean_msg.split()),
                    "reply_to_id": None,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.MESSAGES].update_one({"_id": m_id}, {"$set": m_doc}, upsert=True)
                msg_count += 1

                # Behavior Weekly
                b_id = f"BEH_{s_pid}_{c_id}_W{w}"
                b_doc = {
                    "_id": b_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "week_index": w,
                    "login_count": 5 + w,
                    "session_minutes": 180.0 + (w * 15),
                    "clicks": 45 + (w * 8),
                    "video_play_count": 6 + w,
                    "video_pause_count": 4,
                    "video_rewind_count": 2,
                    "video_skip_count": 1,
                    "video_completion_pct": 88.5,
                    "submissions_count": 1,
                    "avg_submission_delay_hours": -3.5,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.BEHAVIOR_WEEKLY].update_one({"_id": b_id}, {"$set": b_doc}, upsert=True)
                beh_count += 1

                asg_id = f"{c_id}_ASG_W{w}"
                qz_id = f"{c_id}_QZ_W{w}"

                # Grades
                g_id = f"GRD_{s_pid}_{c_id}_W{w}"
                g_doc = {
                    "_id": g_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "week_index": w,
                    "grade_item": f"TMA {w + 1}",
                    "score": 82.0 + (w * 2),
                    "max_score": 100.0,
                    "weight_pct": 25.0,
                    "assessment_id": asg_id,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.GRADES].update_one({"_id": g_id}, {"$set": g_doc}, upsert=True)

                # Attendance
                att_id = f"ATT_{s_pid}_{c_id}_W{w}"
                att_doc = {
                    "_id": att_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "week_index": w,
                    "sessions_scheduled": 4,
                    "sessions_attended": 4,
                    "attendance_pct": 100.0,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.ATTENDANCE].update_one({"_id": att_id}, {"$set": att_doc}, upsert=True)

                # Submissions
                sub_id = f"SUB_{s_pid}_{c_id}_W{w}"
                sub_doc = {
                    "_id": sub_id,
                    "submission_id": sub_id,
                    "assignment_id": asg_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "submitted_at": time_w,
                    "score": 85.0,
                    "delay_hours": -2.5,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.SUBMISSIONS].update_one({"_id": sub_id}, {"$set": sub_doc}, upsert=True)

                # Quiz Attempts
                qa_id = f"QA_{s_pid}_{c_id}_W{w}"
                qa_doc = {
                    "_id": qa_id,
                    "attempt_id": qa_id,
                    "quiz_id": qz_id,
                    "pid": s_pid,
                    "course_id": c_id,
                    "score": 18.0,
                    "completed_at": time_w,
                    "schema_version": 1,
                    "ingested_at": base_time,
                    "source_version": "1.0",
                    "source": "demo",
                }
                db[col.QUIZ_ATTEMPTS].update_one({"_id": qa_id}, {"$set": qa_doc}, upsert=True)

    # ── 7. Seed sample research-exempt OULAD records ──────────────────────────
    oulad_student_pid = generate_pid(99)
    oulad_course = "AAA_2013J"
    oulad_time = datetime(2013, 10, 15, 12, 0, tzinfo=timezone.utc)

    oulad_msg_id = f"MSG_OULAD_{oulad_student_pid}_W1"
    db[col.MESSAGES].update_one(
        {"_id": oulad_msg_id},
        {
            "$set": {
                "_id": oulad_msg_id,
                "message_id": oulad_msg_id,
                "pid": oulad_student_pid,
                "course_id": oulad_course,
                "week_index": 1,
                "source_type": "forum",
                "clean_text": "Public anonymized research forum post from OULAD dataset.",
                "timestamp": oulad_time,
                "message_length_chars": 58,
                "message_length_words": 8,
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
                "source": "oulad",
            }
        },
        upsert=True,
    )

    oulad_beh_id = f"BEH_OULAD_{oulad_student_pid}_W1"
    db[col.BEHAVIOR_WEEKLY].update_one(
        {"_id": oulad_beh_id},
        {
            "$set": {
                "_id": oulad_beh_id,
                "pid": oulad_student_pid,
                "course_id": oulad_course,
                "week_index": 1,
                "login_count": 8,
                "session_minutes": 210.0,
                "clicks": 65,
                "video_play_count": 0,
                "video_pause_count": 0,
                "video_rewind_count": 0,
                "video_skip_count": 0,
                "video_completion_pct": 0.0,
                "submissions_count": 1,
                "avg_submission_delay_hours": -1.0,
                "schema_version": 1,
                "ingested_at": base_time,
                "source_version": "1.0",
                "source": "oulad",
            }
        },
        upsert=True,
    )

    print(f"  [+] Seeded {msg_count + 1} messages, {beh_count + 1} behavioral records, and corresponding academic artifacts.")
    print("[SUCCESS] Component export demo dataset seeded successfully.")


def main():
    parser = argparse.ArgumentParser(description="Seed or remove Component Export demo dataset.")
    parser.add_argument("--remove", action="store_true", help="Remove all demo data tagged with source='demo'.")
    parser.add_argument("--mongo-uri", default=None, help="Override MongoDB connection URI.")
    parser.add_argument("--db-name", default=None, help="Override database name.")

    args = parser.parse_args()
    uri = args.mongo_uri or settings.MONGODB_URI
    db_name = args.db_name or settings.DB_NAME

    client = MongoClient(uri, tz_aware=True)
    try:
        db = client[db_name]
        if args.remove:
            remove_demo_data(db)
        else:
            seed_demo_data(db)
    finally:
        client.close()


if __name__ == "__main__":
    main()
