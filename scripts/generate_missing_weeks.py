"""
scripts/generate_missing_weeks.py

Generates and populates longitudinal data for Week 13, 14, and 15 (week indices 12, 13, 14)
in MongoDB Atlas to complete the 15-week academic semester for courses (e.g. CS101, DEMO101).

Populates:
  - risk_assessments
  - engagement_trajectories
  - behavior_weekly
  - affective_weekly
  - grades
  - attendance
  - course_weeks
"""

import os
import random
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ReplaceOne, UpdateOne

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://nidukavikumasipath_db_user:GmKuIN45W0FOhKK0@cluster0.sqmc74m.mongodb.net/lms_db?retryWrites=true&w=majority&appName=Cluster0"
)

TARGET_COURSES = ["CS101", "DEMO101"]
WEEKS_TO_GENERATE = [12, 13, 14]  # 0-indexed for Weeks 13, 14, 15

DISTRESS_KEYS = [
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion"
]

def main():
    print(f"Connecting to MongoDB Atlas...")
    client = MongoClient(MONGO_URI)
    db = client["lms_db"]
    now_utc = datetime.now(timezone.utc)
    base_time = now_utc - timedelta(days=15 * 7)

    rng = random.Random(2026)

    for course_id in TARGET_COURSES:
        print(f"\n==========================================")
        print(f"Processing course: {course_id}")
        print(f"==========================================")

        # 1. Update/Ensure course_weeks collection for all 15 weeks
        cw_ops = []
        for w in range(15):
            week_id = f"{course_id}_W{w}"
            start = base_time + timedelta(days=w * 7)
            end = start + timedelta(days=7)
            doc = {
                "_id": week_id,
                "course_id": course_id,
                "week_index": w,
                "title": f"Week {w + 1}",
                "start_date": start,
                "end_date": end,
                "schema_version": 1,
                "source_version": "1.0",
                "ingested_at": now_utc,
            }
            cw_ops.append(ReplaceOne({"_id": week_id}, doc, upsert=True))
        if cw_ops:
            db["course_weeks"].bulk_write(cw_ops)
            print(f"  [+] course_weeks updated for 15 weeks.")

        # 2. Find students present in week 11 (Week 12)
        week11_risks = list(db["risk_assessments"].find({"course_id": course_id, "week_index": 11}))
        if not week11_risks:
            # Fallback to any students enrolled
            enrols = list(db["enrolments"].find({"course_id": course_id}))
            pids = [e["pid"] for e in enrols]
            print(f"  No week 11 risk assessments found. Using {len(pids)} enrolled students.")
            student_profiles = [{
                "pid": pid,
                "risk_score": rng.uniform(0.1, 0.7),
                "risk_tier": "medium",
                "source": "synthetic"
            } for pid in pids]
        else:
            print(f"  Found {len(week11_risks)} students at week index 11.")
            student_profiles = [{
                "pid": r["pid"],
                "risk_score": r.get("risk_score", 0.3),
                "risk_tier": r.get("risk_tier", "medium"),
                "source": r.get("source", "synthetic")
            } for r in week11_risks]

        # 3. Generate data for weeks 12, 13, 14
        ra_ops = []
        et_ops = []
        bw_ops = []
        af_ops = []
        grd_ops = []
        att_ops = []

        for sp in student_profiles:
            pid = sp["pid"]
            prev_risk = sp["risk_score"]
            prev_tier = sp["risk_tier"]

            for w in WEEKS_TO_GENERATE:
                doc_id = f"{pid}_{course_id}_{w}"
                progress_factor = (w - 11) / 3.0  # 0.33, 0.66, 1.0

                if prev_tier in ["high", "critical"] or prev_risk >= 0.5:
                    # Declining / critical risk progression
                    risk_score = min(0.98, round(prev_risk + progress_factor * rng.uniform(0.02, 0.08), 3))
                    risk_tier = "critical" if risk_score >= 0.75 else "high"
                    traj_label = "declining"
                    aff_weight = 0.45
                    beh_weight = 0.30
                    acad_weight = 0.25
                    drivers = ["declining_logins", "low_video_completion", "late_submissions", "high_affective_distress"]

                    login_count = max(1, int(4 - progress_factor * 2 + rng.randint(-1, 1)))
                    clicks = max(10, int(45 - progress_factor * 15 + rng.randint(-5, 5)))
                    video_pct = max(5.0, round(40.0 - progress_factor * 20.0 + rng.uniform(-5, 5), 1))
                    session_mins = max(15.0, round(60.0 - progress_factor * 25.0 + rng.uniform(-10, 10), 1))
                    sub_delay = round(3.0 + progress_factor * 3.0 + rng.uniform(-0.5, 1.5), 1)
                    attendance = max(30.0, round(60.0 - progress_factor * 15.0 + rng.uniform(-4, 4), 1))
                    ca_mark = max(20.0, round(50.0 - progress_factor * 18.0 + rng.uniform(-3, 3), 1))

                elif prev_tier == "medium" or (0.3 <= prev_risk < 0.5):
                    # Volatile / moderate risk
                    risk_score = round(prev_risk + rng.uniform(-0.06, 0.08), 3)
                    risk_score = min(max(risk_score, 0.25), 0.65)
                    risk_tier = "medium"
                    traj_label = rng.choice(["volatile", "declining"])
                    aff_weight = 0.40
                    beh_weight = 0.30
                    acad_weight = 0.30
                    drivers = ["conceptual_confusion", "fluctuating_engagement", "erratic_sessions"]

                    login_count = rng.randint(4, 8)
                    clicks = rng.randint(45, 85)
                    video_pct = round(rng.uniform(45.0, 70.0), 1)
                    session_mins = round(rng.uniform(70.0, 140.0), 1)
                    sub_delay = round(rng.uniform(0.5, 3.0), 1)
                    attendance = round(rng.uniform(65.0, 80.0), 1)
                    ca_mark = round(rng.uniform(50.0, 68.0), 1)

                else:
                    # Low risk / stable or improving
                    risk_score = max(0.03, round(prev_risk - progress_factor * rng.uniform(0.01, 0.04), 3))
                    risk_tier = "low"
                    traj_label = "improving"
                    aff_weight = 0.15
                    beh_weight = 0.40
                    acad_weight = 0.45
                    drivers = ["regular_logins", "high_video_completion", "early_submissions"]

                    login_count = rng.randint(8, 15)
                    clicks = rng.randint(110, 200)
                    video_pct = round(rng.uniform(85.0, 99.0), 1)
                    session_mins = round(rng.uniform(160.0, 300.0), 1)
                    sub_delay = round(rng.uniform(-8.0, -1.0), 1)
                    attendance = round(rng.uniform(90.0, 100.0), 1)
                    ca_mark = round(rng.uniform(75.0, 95.0), 1)

                # Risk Assessment Document
                ra_doc = {
                    "_id": doc_id,
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "risk_score": risk_score,
                    "risk_tier": risk_tier,
                    "modality_contributions": {
                        "affective": aff_weight,
                        "behavioral": beh_weight,
                        "academic": acad_weight,
                    },
                    "top_drivers": drivers,
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                ra_ops.append(ReplaceOne({"_id": doc_id}, ra_doc, upsert=True))

                # Trajectory Document
                et_doc = {
                    "_id": doc_id,
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "trajectory_label": traj_label,
                    "confidence": round(rng.uniform(0.82, 0.96), 2),
                    "contributing_indicators": drivers[:3],
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                et_ops.append(ReplaceOne({"_id": doc_id}, et_doc, upsert=True))

                # Behavior Document
                bw_doc = {
                    "_id": doc_id,
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "login_count": login_count,
                    "session_minutes": session_mins,
                    "clicks": clicks,
                    "video_play_count": rng.randint(2, 7),
                    "video_pause_count": rng.randint(1, 5),
                    "video_rewind_count": rng.randint(0, 4),
                    "video_skip_count": rng.randint(0, 2),
                    "video_completion_pct": video_pct,
                    "submissions_count": 1,
                    "avg_submission_delay_hours": sub_delay,
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                bw_ops.append(ReplaceOne({"_id": doc_id}, bw_doc, upsert=True))

                # Affective Document
                stress_tag = "high_stress" if risk_tier in ["high", "critical"] else ("moderate_stress" if risk_tier == "medium" else "calm")
                af_doc = {
                    "_id": doc_id,
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "emotion_scores": {k: round(rng.uniform(0.1, 0.85), 2) for k in DISTRESS_KEYS},
                    "stress_label": stress_tag,
                    "confidence": round(rng.uniform(0.8, 0.95), 2),
                    "message_count": rng.randint(1, 4),
                    "top_drivers": [{"token_or_marker": d, "weight": 0.33} for d in drivers[:3]],
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                af_ops.append(ReplaceOne({"_id": doc_id}, af_doc, upsert=True))

                # Grades Document
                grd_doc = {
                    "_id": f"grd_{doc_id}",
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "grade_item": f"Weekly Assessment W{w+1}",
                    "score": ca_mark,
                    "max_score": 100.0,
                    "weight_pct": 10.0,
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                grd_ops.append(ReplaceOne({"_id": f"grd_{doc_id}"}, grd_doc, upsert=True))

                # Attendance Document
                att_doc = {
                    "_id": f"att_{doc_id}",
                    "pid": pid,
                    "course_id": course_id,
                    "week_index": w,
                    "sessions_scheduled": 2,
                    "sessions_attended": 2 if attendance >= 70.0 else 1,
                    "attendance_pct": attendance,
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": sp.get("source", "synthetic"),
                    "ingested_at": now_utc,
                }
                att_ops.append(ReplaceOne({"_id": f"att_{doc_id}"}, att_doc, upsert=True))

        print(f"  Executing bulk writes for {len(student_profiles)} students across weeks 12, 13, 14...")
        if ra_ops:
            db["risk_assessments"].bulk_write(ra_ops)
            print(f"    [+] risk_assessments: {len(ra_ops)} docs written")
        if et_ops:
            db["engagement_trajectories"].bulk_write(et_ops)
            print(f"    [+] engagement_trajectories: {len(et_ops)} docs written")
        if bw_ops:
            db["behavior_weekly"].bulk_write(bw_ops)
            print(f"    [+] behavior_weekly: {len(bw_ops)} docs written")
        if af_ops:
            db["affective_weekly"].bulk_write(af_ops)
            print(f"    [+] affective_weekly: {len(af_ops)} docs written")
        if grd_ops:
            db["grades"].bulk_write(grd_ops)
            print(f"    [+] grades: {len(grd_ops)} docs written")
        if att_ops:
            db["attendance"].bulk_write(att_ops)
            print(f"    [+] attendance: {len(att_ops)} docs written")

    # 4. Final verification of weeks across collections
    print("\n==========================================")
    print("VERIFICATION OF AVAILABLE WEEKS")
    print("==========================================")
    for c in TARGET_COURSES:
        weeks = db["risk_assessments"].distinct("week_index", {"course_id": c})
        print(f"Course '{c}' distinct weeks in risk_assessments: {sorted(weeks)}")

    client.close()
    print("\nCompleted successfully!")

if __name__ == "__main__":
    main()
