"""
scripts/send_sample_ingest.py

Feature 23: Sample Sender and Verification Tool for ML Component Ingestion.
Builds valid Feature 24 contract envelopes for demo students and submits them to:
  - C1: POST /api/v1/ingest/affective
  - C2: POST /api/v1/ingest/trajectory
  - C3: POST /api/v1/ingest/risk
  - C4: POST /api/v1/ingest/recommendations

Features:
  - Reads preshared component API keys from COMPONENT_API_KEYS (never logs/prints secret keys)
  - Supports --dry-run (validates pipeline without persisting changes)
  - Supports --base-url (default http://localhost:8000)
  - Supports --remove to clean up only records created by this tool (source="demo")
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
for p in ["/", "/app", str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[0])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

import httpx
from pymongo import MongoClient

from app.core.config import settings
from app.db import collections as col

INGEST_COLLECTIONS = [
    col.AFFECTIVE_WEEKLY,
    col.ENGAGEMENT_TRAJECTORIES,
    col.RISK_ASSESSMENTS,
    col.RECOMMENDATIONS,
    col.INGESTION_RUNS,
    col.IDENTITY_VAULT,
    col.CONSENT_RECORDS,
    col.ENROLMENTS,
]


def generate_pid(index: int) -> str:
    """Generates deterministic Feature 5 compliant PID."""
    digest = hashlib.sha256(f"demo_export_student_ident_{index}".encode("utf-8")).hexdigest()
    return f"STU_{digest[:8]}"


def get_configured_keys() -> Dict[str, str]:
    """Retrieves component API keys from environment or settings."""
    raw_env = os.environ.get("COMPONENT_API_KEYS")
    if raw_env:
        try:
            parsed = json.loads(raw_env)
            if isinstance(parsed, dict):
                return {str(k).lower().strip(): str(v).strip() for k, v in parsed.items()}
        except Exception:
            pass
    return settings.COMPONENT_API_KEYS


def remove_demo_records(mongo_uri: str, db_name: str) -> None:
    """Removes all documents created with source='demo' across ingestion collections."""
    print(f"Connecting to MongoDB database '{db_name}' for cleanup...")
    client = MongoClient(mongo_uri, tz_aware=True)
    try:
        db = client[db_name]
        total_deleted = 0
        for collection_name in INGEST_COLLECTIONS:
            res = db[collection_name].delete_many({"source": "demo"})
            if res.deleted_count > 0:
                print(f"  [-] Deleted {res.deleted_count} demo doc(s) from '{collection_name}'.")
                total_deleted += res.deleted_count
        print(f"[CLEANUP COMPLETE] Total ingestion demo records removed: {total_deleted}")
    finally:
        client.close()


def find_consenting_enrolled_student(mongo_uri: str, db_name: str) -> Dict[str, str]:
    """Finds or creates a student PID and course that has identity vault, active consent, and active enrolment."""
    client = MongoClient(mongo_uri, tz_aware=True)
    try:
        db = client[db_name]
        notice = db[col.CONSENT_NOTICES].find_one({"is_active": True})
        notice_ver = notice["version"] if notice else 1

        vault_pids = set(db[col.IDENTITY_VAULT].distinct("pid"))
        if vault_pids:
            consenting_pids = set(
                db[col.CONSENT_RECORDS].distinct("pid", {"notice_version": notice_ver, "decision": "accepted"})
            )
            # Find enrolled student with consent and vault
            candidate = db[col.ENROLMENTS].find_one({
                "pid": {"$in": list(consenting_pids & vault_pids)},
                "status": {"$in": ["active", "completed"]},
            })
            if candidate:
                return {"pid": candidate["pid"], "course_id": str(candidate["course_id"])}

            # Or find enrolled student in vault and add accepted consent
            enrolled_in_vault = db[col.ENROLMENTS].find_one({
                "pid": {"$in": list(vault_pids)},
                "status": {"$in": ["active", "completed"]},
            })
            if enrolled_in_vault:
                pid = enrolled_in_vault["pid"]
                cid = str(enrolled_in_vault["course_id"])
                now_utc = datetime.now(timezone.utc)
                db[col.CONSENT_RECORDS].update_one(
                    {"_id": f"demo_consent_{pid}"},
                    {
                        "$set": {
                            "_id": f"demo_consent_{pid}",
                            "pid": pid,
                            "notice_version": notice_ver,
                            "decision": "accepted",
                            "timestamp": now_utc,
                            "ip_or_client": "127.0.0.1",
                            "source": "demo",
                        }
                    },
                    upsert=True,
                )
                return {"pid": pid, "course_id": cid}

        # Fallback: create complete demo student with source='demo'
        demo_pid = generate_pid(0)
        demo_cid = "DEMO101"
        now_utc = datetime.now(timezone.utc)
        db[col.IDENTITY_VAULT].update_one(
            {"_id": demo_pid},
            {
                "$set": {
                    "_id": demo_pid,
                    "pid": demo_pid,
                    "student_id": "DEMO_STUDENT_001",
                    "name": "Demo Ingest Student",
                    "email": "demo_ingest@example.com",
                    "schema_version": 1,
                    "ingested_at": now_utc,
                    "source_version": "1.0",
                    "source": "demo",
                }
            },
            upsert=True,
        )
        db[col.CONSENT_RECORDS].update_one(
            {"_id": f"demo_consent_{demo_pid}"},
            {
                "$set": {
                    "_id": f"demo_consent_{demo_pid}",
                    "pid": demo_pid,
                    "notice_version": notice_ver,
                    "decision": "accepted",
                    "timestamp": now_utc,
                    "ip_or_client": "127.0.0.1",
                    "source": "demo",
                }
            },
            upsert=True,
        )
        db[col.ENROLMENTS].update_one(
            {"_id": f"{demo_pid}_{demo_cid}"},
            {
                "$set": {
                    "_id": f"{demo_pid}_{demo_cid}",
                    "pid": demo_pid,
                    "course_id": demo_cid,
                    "enrolment_start": now_utc,
                    "status": "active",
                    "schema_version": 1,
                    "ingested_at": now_utc,
                    "source_version": "1.0",
                    "source": "demo",
                }
            },
            upsert=True,
        )
        return {"pid": demo_pid, "course_id": demo_cid}
    except Exception as exc:
        print(f"[WARN] Error querying MongoDB for demo student: {exc}. Using deterministic fallback.")
        return {"pid": generate_pid(0), "course_id": "DEMO101"}
    finally:
        client.close()


def send_samples(base_url: str, dry_run: bool, student_info: Dict[str, str]) -> None:
    keys = get_configured_keys()
    if not keys:
        print("[ERROR] No COMPONENT_API_KEYS configured in environment or settings. Cannot proceed.")
        sys.exit(1)

    pid = student_info["pid"]
    course_id = student_info["course_id"]
    now_iso = datetime.now(timezone.utc).isoformat()
    client = httpx.Client(base_url=base_url, timeout=30.0)

    print(f"Submitting sample payloads to {base_url} (dry_run={dry_run})...")
    print(f"Target student: {pid} | Course: {course_id}\n")

    endpoints = [
        {
            "name": "C1 Affective Weekly Vector",
            "path": "/api/v1/ingest/affective",
            "component": "c1",
            "payload": {
                "schema_version": "1.0",
                "generated_at": now_iso,
                "source": "c1",
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
                "data": [
                    {
                        "pid": pid,
                        "course_id": course_id,
                        "week_index": 0,
                        "emotion_scores": {
                            "exam_anxiety": 0.35,
                            "conceptual_confusion": 0.20,
                            "academic_helplessness": 0.10,
                            "course_frustration": 0.15,
                            "motivation_erosion": 0.05,
                        },
                        "stress_label": "moderate",
                        "confidence": 0.88,
                        "message_count": 4,
                        "top_drivers": [
                            {"token_or_marker": "midterm_exam", "weight": 0.65},
                            {"token_or_marker": "recursion_lab", "weight": 0.35},
                        ],
                    }
                ],
            },
        },
        {
            "name": "C2 Engagement Trajectory",
            "path": "/api/v1/ingest/trajectory",
            "component": "c2",
            "payload": {
                "schema_version": "1.0",
                "generated_at": now_iso,
                "source": "c2",
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
                "data": [
                    {
                        "pid": pid,
                        "course_id": course_id,
                        "week_index": 0,
                        "trajectory_label": "stable",
                        "confidence": 0.92,
                        "contributing_indicators": [
                            "daily_portal_logins",
                            "on_time_lab_submissions",
                        ],
                    }
                ],
            },
        },
        {
            "name": "C3 Multimodal Risk Assessment",
            "path": "/api/v1/ingest/risk",
            "component": "c3",
            "payload": {
                "schema_version": "1.0",
                "generated_at": now_iso,
                "source": "c3",
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
                "data": [
                    {
                        "pid": pid,
                        "course_id": course_id,
                        "week_index": 0,
                        "risk_score": 0.28,
                        "risk_tier": "low",
                        "modality_contributions": {
                            "affective": 0.30,
                            "behavioral": 0.35,
                            "academic": 0.35,
                        },
                        "top_drivers": [
                            "consistent_lecture_attendance",
                            "high_quiz_average",
                        ],
                    }
                ],
            },
        },
        {
            "name": "C4 Intervention Recommendations",
            "path": "/api/v1/ingest/recommendations",
            "component": "c4",
            "payload": {
                "schema_version": "1.0",
                "generated_at": now_iso,
                "source": "c4",
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
                "data": [
                    {
                        "recommendation_id": f"REC_SAMPLE_{pid}_W0",
                        "pid": pid,
                        "week_index": 0,
                        "candidates": [
                            {
                                "intervention_type": "peer_tutoring",
                                "suitability_score": 0.85,
                                "rationale": "Recommended for algorithmic problem solving reinforcement.",
                                "rank": 1,
                            },
                            {
                                "intervention_type": "academic_advising",
                                "suitability_score": 0.70,
                                "rationale": "Periodic check-in on midterm preparation.",
                                "rank": 2,
                            },
                        ],
                        "status": "proposed",
                    }
                ],
            },
        },
    ]

    for item in endpoints:
        comp_id = item["component"]
        secret_key = keys.get(comp_id)
        if not secret_key:
            print(f"[SKIP] Key for component '{comp_id}' not configured in COMPONENT_API_KEYS.")
            continue

        url = f"{item['path']}?source=demo"
        if dry_run:
            url += "&dry_run=true"

        headers = {
            "Content-Type": "application/json",
            "X-Component-Key": secret_key,
        }

        try:
            resp = client.post(url, headers=headers, json=item["payload"])
            if resp.status_code == 200:
                res_data = resp.json()
                print(f"[OK] {item['name']}: HTTP 200")
                print(f"     Run ID:   {res_data.get('run_id')}")
                print(f"     Received: {res_data.get('received')} | Accepted: {res_data.get('accepted')} | Rejected: {res_data.get('rejected')}")
                print(f"     Created:  {res_data.get('created')} | Updated:  {res_data.get('updated')}")
                if res_data.get("rejected_records"):
                    print(f"     Rejections: {res_data.get('rejected_records')}")
            else:
                print(f"[FAIL] {item['name']}: HTTP {resp.status_code}")
                print(f"       Response: {resp.text[:200]}")
        except Exception as exc:
            print(f"[ERR] Error posting to {item['name']}: {exc}")

    print("\n[COMPLETE] Sample ingestion run finished.")


def main():
    parser = argparse.ArgumentParser(description="Send sample component output payloads to LMS Ingestion API.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="LMS backend API base URL.")
    parser.add_argument("--dry-run", action="store_true", help="Validate payloads without database persistence.")
    parser.add_argument("--remove", action="store_true", help="Delete demo output documents from database.")
    parser.add_argument("--mongo-uri", default=None, help="MongoDB connection URI for cleanup.")
    parser.add_argument("--db-name", default=None, help="Database name for cleanup.")

    args = parser.parse_args()
    uri = args.mongo_uri or settings.MONGODB_URI
    db_name = args.db_name or settings.DB_NAME

    if args.remove:
        remove_demo_records(uri, db_name)
        return

    student = find_consenting_enrolled_student(uri, db_name)
    send_samples(base_url=args.base_url, dry_run=args.dry_run, student_info=student)


if __name__ == "__main__":
    main()
