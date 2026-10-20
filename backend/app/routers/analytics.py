"""
backend/app/routers/analytics.py

Feature 27: Cohort Risk Overview Dashboard
Feature 28: Student Risk Detail View
Feature 29: Engagement Trajectory View
Feature 41: Synthetic Data Generator

Provides cohort-level early warning risk telemetry, longitudinal engagement trajectory
analytics, individual student multimodal diagnostic breakdowns, and a realistic
synthetic data generator for institutional simulations and ML research.
"""

import asyncio
from datetime import datetime, timezone
import random
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import ReplaceOne, UpdateOne

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.db import collections as col
from app.db.storage_models import (
    AffectiveWeeklyStorage,
    AttendanceStorage,
    BehaviorWeeklyStorage,
    EngagementTrajectoryStorage,
    GradeStorage,
    IdentityVaultStorage,
    RiskAssessmentStorage,
    TextMessageStorage,
)
from app.models.user import User, UserRole
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.contract.common import (
    CleanText,
    DistressClass,
    RiskTier,
    SourceType,
    TrajectoryLabel,
)
from app.schemas.contract.v1 import ModalityContributions, TopDriver
from app.services.audit import log_event

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ── Pydantic Request Models ───────────────────────────────────────────────────

class SyntheticCohortGenerateRequest(BaseModel):
    course_id: str = Field(default="CS101", min_length=1, max_length=128)
    num_students: int = Field(default=10, ge=2, le=50)
    num_weeks: int = Field(default=6, ge=1, le=12)
    cohort_profile: str = Field(
        default="balanced",
        description="Distribution profile: balanced, high_risk_heavy, healthy_cohort, or volatile"
    )
    clear_existing: bool = Field(default=False)


# ── Realistic Names Pool for Synthetic Generator ──────────────────────────────

FIRST_NAMES = [
    "Kasun", "Amaya", "Dilan", "Sachini", "Nuwan", "Tharushi", "Chamath", "Nethmi",
    "Kavindu", "Shenali", "Dinuka", "Isuru", "Rashmi", "Janith", "Anuki", "Malith",
    "Sanduni", "Lakshan", "Hiruni", "Sahan", "Kaveesha", "Praveen", "Hansani", "Roshan",
    "Kavya", "Supun", "Dulani", "Ashan", "Pavithra", "Ravindu"
]

LAST_NAMES = [
    "Perera", "Fernando", "Silva", "Jayawardena", "Bandara", "De Silva", "Senaratne",
    "Wickramasinghe", "Rathnayake", "Peiris", "Jayasuriya", "Herath", "Alwis", "Abeykoon",
    "Gamage", "Gunawardena", "Liyanage", "Dissanayake", "Karunaratne", "Samarasinghe"
]


# ── Feature 27: Cohort Risk Overview Endpoint ─────────────────────────────────

@router.get(
    "/cohort-risk",
    summary="Cohort Risk Overview Dashboard (Feature 27)",
    description="Returns cohort-level risk distribution, trajectory overview, modality weights, and filterable student roster.",
    status_code=status.HTTP_200_OK,
)
async def get_cohort_risk_overview(
    course_id: Optional[str] = Query(None, description="Course identifier (e.g. CS101, SE4020)"),
    week_index: Optional[int] = Query(None, ge=0, description="Optional academic week index filter"),
    risk_tier: Optional[str] = Query(None, description="Filter by risk tier: low, medium, high, critical, or all"),
    trajectory: Optional[str] = Query(None, description="Filter by trajectory: stable, improving, declining, volatile, or all"),
    search: Optional[str] = Query(None, description="Search by name, student_id, or PID"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LECTURER)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # 1. Fetch available courses
    courses_cursor = db[col.COURSES].find({}, {"_id": 1, "title": 1, "course_code": 1})
    courses_docs = await courses_cursor.to_list(100)
    available_courses = [
        {
            "id": str(c["_id"]),
            "title": c.get("title", str(c["_id"])),
            "course_code": c.get("course_code", str(c["_id"])),
        }
        for c in courses_docs
    ]

    selected_course_id = course_id
    if not selected_course_id and available_courses:
        selected_course_id = available_courses[0]["id"]
    elif not selected_course_id:
        selected_course_id = "CS101"

    # Find course title
    selected_course_title = selected_course_id
    for c in available_courses:
        if c["id"] == selected_course_id or c["course_code"] == selected_course_id:
            selected_course_title = c["title"]
            break

    # 2. Find available weeks for this course
    weeks_distinct = await db[col.RISK_ASSESSMENTS].distinct("week_index", {"course_id": selected_course_id})
    if not weeks_distinct:
        # Fallback query if course_id might match by title or code
        weeks_distinct = await db[col.RISK_ASSESSMENTS].distinct("week_index", {})
    available_weeks = sorted([w for w in weeks_distinct if isinstance(w, int)])

    selected_week = week_index
    if selected_week is None:
        selected_week = max(available_weeks) if available_weeks else 0

    # 3. Query risk assessments for the cohort
    filter_query: Dict[str, Any] = {"course_id": selected_course_id}
    if available_weeks:
        filter_query["week_index"] = selected_week

    risk_docs = await db[col.RISK_ASSESSMENTS].find(filter_query).to_list(500)

    # If empty, check if documents exist without course_id match or all courses
    if not risk_docs and not course_id:
        # Load any available risk docs
        any_course = await db[col.RISK_ASSESSMENTS].find_one({})
        if any_course and "course_id" in any_course:
            selected_course_id = any_course["course_id"]
            filter_query["course_id"] = selected_course_id
            weeks_distinct = await db[col.RISK_ASSESSMENTS].distinct("week_index", {"course_id": selected_course_id})
            available_weeks = sorted([w for w in weeks_distinct if isinstance(w, int)])
            selected_week = max(available_weeks) if available_weeks else 0
            filter_query["week_index"] = selected_week
            risk_docs = await db[col.RISK_ASSESSMENTS].find(filter_query).to_list(500)

    # 4. Fetch associated trajectories for these students in this week
    pids = list({d["pid"] for d in risk_docs if "pid" in d})
    traj_cursor = db[col.ENGAGEMENT_TRAJECTORIES].find({
        "course_id": selected_course_id,
        "week_index": selected_week,
        "pid": {"$in": pids},
    })
    traj_docs = await traj_cursor.to_list(len(pids) + 10)
    traj_map = {t["pid"]: t for t in traj_docs}

    # 5. Fetch identity vault mappings
    iv_cursor = db[col.IDENTITY_VAULT].find({"pid": {"$in": pids}})
    iv_docs = await iv_cursor.to_list(len(pids) + 10)
    iv_map = {iv["pid"]: iv for iv in iv_docs}

    # 6. Aggregate metrics
    tier_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    trajectory_counts = {"declining": 0, "stable": 0, "improving": 0, "volatile": 0}
    total_risk = 0.0
    total_aff = 0.0
    total_beh = 0.0
    total_acad = 0.0

    students_list = []

    for r in risk_docs:
        pid = r["pid"]
        tier = str(r.get("risk_tier", "low")).lower()
        score = float(r.get("risk_score", 0.0))
        mods = r.get("modality_contributions", {}) or {}
        aff = float(mods.get("affective", 0.33))
        beh = float(mods.get("behavioral", 0.34))
        acad = float(mods.get("academic", 0.33))

        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total_risk += score
        total_aff += aff
        total_beh += beh
        total_acad += acad

        # Trajectory info
        t_data = traj_map.get(pid, {})
        t_label = str(t_data.get("trajectory_label", "stable")).lower()
        trajectory_counts[t_label] = trajectory_counts.get(t_label, 0) + 1

        # Determine primary modality driver
        mod_pairs = [("Affective", aff), ("Behavioral", beh), ("Academic", acad)]
        primary_mod = max(mod_pairs, key=lambda x: x[1])[0]

        # Identity info
        id_info = iv_map.get(pid, {})
        student_name = id_info.get("name") or f"Student {pid[-4:]}"
        student_id_val = id_info.get("student_id") or f"IT{abs(hash(pid)) % 100000000:08d}"
        email_val = id_info.get("email") or f"{pid.lower()}@students.lms.edu"

        student_row = {
            "pid": pid,
            "student_id": student_id_val,
            "name": student_name,
            "email": email_val,
            "risk_score": round(score, 3),
            "risk_tier": tier,
            "trajectory_label": t_label,
            "trajectory_confidence": round(float(t_data.get("confidence", 0.85)), 2),
            "modality_contributions": {
                "affective": round(aff, 3),
                "behavioral": round(beh, 3),
                "academic": round(acad, 3),
            },
            "primary_driver_modality": primary_mod,
            "top_drivers": r.get("top_drivers", []),
            "contributing_indicators": t_data.get("contributing_indicators", []),
            "week_index": r.get("week_index", selected_week),
        }
        students_list.append(student_row)

    total_count = len(students_list)
    avg_risk = round(total_risk / total_count, 3) if total_count > 0 else 0.0
    avg_aff = round(total_aff / total_count, 3) if total_count > 0 else 0.33
    avg_beh = round(total_beh / total_count, 3) if total_count > 0 else 0.34
    avg_acad = round(total_acad / total_count, 3) if total_count > 0 else 0.33
    high_critical_count = tier_counts.get("critical", 0) + tier_counts.get("high", 0)
    high_risk_pct = round((high_critical_count / total_count) * 100, 1) if total_count > 0 else 0.0

    # 7. Apply In-Memory Filters (tier, trajectory, search)
    filtered_students = students_list
    if risk_tier and risk_tier.lower() != "all":
        filtered_students = [s for s in filtered_students if s["risk_tier"] == risk_tier.lower()]
    if trajectory and trajectory.lower() != "all":
        filtered_students = [s for s in filtered_students if s["trajectory_label"] == trajectory.lower()]
    if search:
        s_term = search.strip().lower()
        filtered_students = [
            s for s in filtered_students
            if s_term in s["name"].lower()
            or s_term in s["student_id"].lower()
            or s_term in s["pid"].lower()
            or any(s_term in d.lower() for d in s["top_drivers"])
        ]

    # Sort descending by risk score
    filtered_students.sort(key=lambda s: s["risk_score"], reverse=True)

    return {
        "course_id": selected_course_id,
        "course_title": selected_course_title,
        "available_courses": available_courses,
        "current_week": selected_week,
        "available_weeks": available_weeks,
        "summary": {
            "total_students": total_count,
            "avg_risk_score": avg_risk,
            "high_risk_percentage": high_risk_pct,
            "tier_distribution": tier_counts,
            "trajectory_distribution": trajectory_counts,
            "avg_modality_contributions": {
                "affective": avg_aff,
                "behavioral": avg_beh,
                "academic": avg_acad,
            },
        },
        "students": filtered_students,
    }


# ── Feature 28 & 29: Student Risk & Trajectory Detail Endpoint ────────────────

@router.get(
    "/students/{pid}/detail",
    summary="Student Risk Detail & Longitudinal Trajectory View (Features 28 & 29)",
    description="Returns deep longitudinal multimodal breakdown, weekly clickstream/telemetry, and cause-matched interventions.",
    status_code=status.HTTP_200_OK,
)
async def get_student_risk_detail(
    pid: str,
    course_id: Optional[str] = Query(None, description="Course identifier (optional)"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # Enforce access control: students can only view their own PID
    if current_user.role == UserRole.STUDENT and current_user.pid != pid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Students may only view their own risk profile.",
        )

    # 1. Resolve Identity
    iv_doc = await db[col.IDENTITY_VAULT].find_one({"pid": pid})
    student_name = iv_doc.get("name") if iv_doc else f"Student {pid[-4:]}"
    student_id = iv_doc.get("student_id") if iv_doc else f"IT{abs(hash(pid)) % 100000000:08d}"
    email = iv_doc.get("email") if iv_doc else f"{pid.lower()}@students.lms.edu"

    # 2. Find course identifier
    target_course_id = course_id
    if not target_course_id:
        sample_ra = await db[col.RISK_ASSESSMENTS].find_one({"pid": pid})
        if sample_ra:
            target_course_id = sample_ra.get("course_id", "CS101")
        else:
            target_course_id = "CS101"

    course_doc = await db[col.COURSES].find_one({"_id": target_course_id})
    course_title = course_doc.get("title", target_course_id) if course_doc else target_course_id

    # 3. Longitudinal Queries (ordered by week_index ASC)
    ra_docs = await db[col.RISK_ASSESSMENTS].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)

    traj_docs = await db[col.ENGAGEMENT_TRAJECTORIES].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)
    traj_by_week = {t["week_index"]: t for t in traj_docs}

    beh_docs = await db[col.BEHAVIOR_WEEKLY].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)
    beh_by_week = {b["week_index"]: b for b in beh_docs}

    grades_docs = await db[col.GRADES].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)
    grades_by_week = {g["week_index"]: g for g in grades_docs}

    att_docs = await db[col.ATTENDANCE].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)
    att_by_week = {a["week_index"]: a for a in att_docs}

    aff_docs = await db[col.AFFECTIVE_WEEKLY].find(
        {"pid": pid, "course_id": target_course_id}
    ).sort("week_index", 1).to_list(50)
    aff_by_week = {af["week_index"]: af for af in aff_docs}

    # 4. Build Longitudinal Trend Series
    all_weeks = sorted(list({r["week_index"] for r in ra_docs} | set(beh_by_week.keys())))
    longitudinal_trends = []

    latest_ra = ra_docs[-1] if ra_docs else None
    latest_traj = traj_docs[-1] if traj_docs else None

    for w in all_weeks:
        r_item = next((r for r in ra_docs if r.get("week_index") == w), None)
        t_item = traj_by_week.get(w, {})
        b_item = beh_by_week.get(w, {})
        g_item = grades_by_week.get(w, {})
        att_item = att_by_week.get(w, {})
        af_item = aff_by_week.get(w, {})

        mods = r_item.get("modality_contributions", {}) if r_item else {}
        risk_val = float(r_item.get("risk_score", 0.0)) if r_item else 0.0

        point = {
            "week_index": w,
            "week_label": f"Week {w + 1}",
            "risk_score": round(risk_val, 3),
            "risk_tier": str(r_item.get("risk_tier", "low")).lower() if r_item else "low",
            "affective_pct": round(float(mods.get("affective", 0.33)) * 100, 1),
            "behavioral_pct": round(float(mods.get("behavioral", 0.34)) * 100, 1),
            "academic_pct": round(float(mods.get("academic", 0.33)) * 100, 1),
            "trajectory_label": str(t_item.get("trajectory_label", "stable")).lower(),
            "trajectory_confidence": round(float(t_item.get("confidence", 0.8)), 2),
            "login_count": b_item.get("login_count", 0),
            "session_minutes": round(float(b_item.get("session_minutes", 0.0)), 1),
            "clicks": b_item.get("clicks", 0),
            "video_completion_pct": round(float(b_item.get("video_completion_pct", 0.0)), 1),
            "submissions_count": b_item.get("submissions_count", 0),
            "avg_submission_delay_hours": round(float(b_item.get("avg_submission_delay_hours", 0.0)), 1),
            "attendance_pct": round(float(att_item.get("attendance_pct", 85.0)), 1),
            "ca_marks": g_item.get("score"),
            "stress_label": af_item.get("stress_label"),
            "top_drivers": r_item.get("top_drivers", []) if r_item else [],
            "contributing_indicators": t_item.get("contributing_indicators", []),
            "has_trajectory": True if w in traj_by_week else False,
        }
        longitudinal_trends.append(point)

    # 5. Cause-Matched Intervention Recommendations
    recommendations = []
    latest_tier = str(latest_ra.get("risk_tier", "low")).lower() if latest_ra else "low"
    latest_mods = latest_ra.get("modality_contributions", {}) if latest_ra else {}
    aff_w = float(latest_mods.get("affective", 0.33))
    beh_w = float(latest_mods.get("behavioral", 0.34))
    acad_w = float(latest_mods.get("academic", 0.33))

    if latest_tier in ["critical", "high"]:
        if aff_w >= max(beh_w, acad_w):
            recommendations.append({
                "category": "Affective & Wellbeing",
                "title": "Empathetic 1-on-1 Academic Advising",
                "description": "High affective distress signals detected (conceptual confusion and anxiety). Schedule a supportive 15-minute consultation to clarify difficult topics.",
                "urgency": "Immediate (Within 24 Hours)",
                "action_type": "1_on_1_meeting",
            })
            recommendations.append({
                "category": "Curricular Adjustment",
                "title": "Provide Conceptual FAQ / Supplementary Walkthrough",
                "description": "Share curated micro-lecture summaries and past worked examples for recent modules.",
                "urgency": "Within 48h",
                "action_type": "supplementary_resources",
            })
        elif beh_w >= max(aff_w, acad_w):
            recommendations.append({
                "category": "Behavioral Re-engagement",
                "title": "Automated Personalized Catch-up Nudge",
                "description": "Declining video playback completion and lower portal login frequencies observed. Send an encouraging check-in reminder with priority tasks.",
                "urgency": "Within 48h",
                "action_type": "encouragement_nudge",
            })
            recommendations.append({
                "category": "Study Strategy",
                "title": "Time Management & Study Plan Template",
                "description": "Recommend flexible study milestones to address deadline slippage.",
                "urgency": "Routine",
                "action_type": "study_plan",
            })
        else:
            recommendations.append({
                "category": "Academic Remediation",
                "title": "Peer Tutoring & TA Lab Session Assignment",
                "description": "Academic submissions indicate low formative quiz retention. Connect student with course teaching assistant for review.",
                "urgency": "Immediate (Within 24 Hours)",
                "action_type": "peer_tutoring",
            })
            recommendations.append({
                "category": "Assessment Accommodation",
                "title": "Formative Practice Quiz with Instant Feedback",
                "description": "Unlock ungraded formative diagnostic quiz to reinforce weak concepts before summative exams.",
                "urgency": "Routine",
                "action_type": "supplementary_resources",
            })
    elif latest_tier == "medium":
        recommendations.append({
            "category": "Proactive Monitoring",
            "title": "Formative Progress Check-in",
            "description": "Moderate risk indicators observed. Verify student comprehension of current milestone assignments.",
            "urgency": "Within 48h",
            "action_type": "encouragement_nudge",
        })
    else:
        recommendations.append({
            "category": "Positive Reinforcement",
            "title": "High Engagement Commendation",
            "description": "Student exhibits healthy engagement trajectory and low risk metrics. Keep up positive learning momentum.",
            "urgency": "Routine",
            "action_type": "encouragement_nudge",
        })

    return {
        "student": {
            "pid": pid,
            "student_id": student_id,
            "name": student_name,
            "email": email,
            "course_id": target_course_id,
            "course_title": course_title,
        },
        "latest_assessment": {
            "week_index": latest_ra.get("week_index", 0) if latest_ra else 0,
            "risk_score": round(float(latest_ra.get("risk_score", 0.0)), 3) if latest_ra else 0.0,
            "risk_tier": latest_tier,
            "modality_contributions": {
                "affective": round(aff_w, 3),
                "behavioral": round(beh_w, 3),
                "academic": round(acad_w, 3),
            },
            "top_drivers": latest_ra.get("top_drivers", []) if latest_ra else [],
            "trajectory_label": str(latest_traj.get("trajectory_label", "stable")).lower() if latest_traj else "stable",
            "trajectory_confidence": round(float(latest_traj.get("confidence", 0.85)), 2) if latest_traj else 0.85,
            "contributing_indicators": latest_traj.get("contributing_indicators", []) if latest_traj else [],
        },
        "longitudinal_trends": longitudinal_trends,
        "recommended_interventions": recommendations,
    }


# ── Feature 41: Synthetic Data Generator Endpoint ─────────────────────────────

@router.post(
    "/synthetic/generate",
    summary="Generate Synthetic Cohort & Multimodal Telemetry Data (Feature 41)",
    description="Generates realistic student cohorts with weekly behavioral logs, affective vectors, academic records, and risk assessments.",
    status_code=status.HTTP_201_CREATED,
)
async def generate_synthetic_cohort_data(
    payload: SyntheticCohortGenerateRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LECTURER)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    course_id = payload.course_id.strip()
    num_students = payload.num_students
    num_weeks = payload.num_weeks
    profile = payload.cohort_profile.lower()

    # 1. Clear existing course data if requested
    if payload.clear_existing:
        await asyncio.gather(
            db[col.RISK_ASSESSMENTS].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.ENGAGEMENT_TRAJECTORIES].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.BEHAVIOR_WEEKLY].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.AFFECTIVE_WEEKLY].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.GRADES].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.ATTENDANCE].delete_many({"course_id": course_id, "source": "synthetic"}),
            db[col.MESSAGES].delete_many({"course_id": course_id, "source": "synthetic"}),
        )

    # Ensure course exists in COURSES collection
    course_doc = await db[col.COURSES].find_one({"_id": course_id})
    if not course_doc:
        course_name = f"Course {course_id}"
        if course_id == "CS101":
            course_name = "Introduction to Computer Systems"
        elif course_id == "SE4020":
            course_name = "Advanced Software Engineering"
        await db[col.COURSES].insert_one({
            "_id": course_id,
            "title": course_name,
            "course_code": course_id,
            "description": "Synthetic demonstration course environment.",
            "is_published": True,
            "created_at": datetime.now(timezone.utc),
        })

    # 2. Generate Student Identities
    created_students = []
    rng = random.Random(42 + hash(course_id) % 1000)
    vault_ops = []
    enr_ops = []
    now_dt = datetime.now(timezone.utc)

    # Assign student persona profiles based on cohort_profile
    for i in range(num_students):
        # Unique deterministic PID
        hex_suffix = f"{abs(hash(f'{course_id}_{i}')) % 0xFFFFFFFF:08x}"
        pid = f"STU_{hex_suffix}"
        student_num = 20000000 + i * 37 + (abs(hash(course_id)) % 50000)
        student_id_str = f"IT{student_num:08d}"
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}@students.lms.edu"

        # Persona determination:
        # 0 = High / Critical Risk (Declining)
        # 1 = Moderate Risk (Volatile / Conceptually Confused)
        # 2 = Low Risk / Consistent Performer (Stable or Improving)
        if profile == "high_risk_heavy":
            persona = rng.choices([0, 1, 2], weights=[0.55, 0.30, 0.15])[0]
        elif profile == "healthy_cohort":
            persona = rng.choices([0, 1, 2], weights=[0.05, 0.20, 0.75])[0]
        elif profile == "volatile":
            persona = rng.choices([0, 1, 2], weights=[0.25, 0.55, 0.20])[0]
        else:  # balanced
            persona = rng.choices([0, 1, 2], weights=[0.25, 0.35, 0.40])[0]

        created_students.append({
            "pid": pid,
            "student_id": student_id_str,
            "name": full_name,
            "email": email,
            "persona": persona,
        })

        # Save to identity vault (bulk op)
        vault_ops.append(
            UpdateOne(
                {"pid": pid},
                {
                    "$set": {
                        "_id": pid,
                        "pid": pid,
                        "student_id": student_id_str,
                        "name": full_name,
                        "email": email,
                        "is_imported": True,
                        "updated_at": now_dt,
                    },
                    "$setOnInsert": {"created_at": now_dt},
                },
                upsert=True,
            )
        )

        # Ensure enrollment document exists (bulk op)
        enr_id = f"enr_{pid}_{course_id}"
        enr_ops.append(
            ReplaceOne(
                {"_id": enr_id},
                {
                    "_id": enr_id,
                    "pid": pid,
                    "course_id": course_id,
                    "status": "active",
                    "enrolment_start": now_dt,
                    "schema_version": 1,
                    "source_version": "1.0",
                    "source": "synthetic",
                    "ingested_at": now_dt,
                },
                upsert=True,
            )
        )

    # 3. Generate Multimodal Telemetry and Risk Data Week-by-Week (Accumulate into bulk batches)
    now_utc = datetime.now(timezone.utc)
    ra_ops = []
    et_ops = []
    bw_ops = []
    grade_ops = []
    att_ops = []
    af_ops = []
    msg_ops = []

    for student in created_students:
        pid = student["pid"]
        persona = student["persona"]

        for w in range(num_weeks):
            doc_id = f"{pid}_{course_id}_{w}"

            # Calculate metrics tailored to persona and week index progression
            if persona == 0:
                # High Risk / Declining: worsening over time
                base_risk = 0.55 + (w / max(num_weeks, 1)) * 0.35
                noise = rng.uniform(-0.05, 0.05)
                risk_score = min(max(round(base_risk + noise, 3), 0.1), 0.98)
                risk_tier = RiskTier.CRITICAL if risk_score >= 0.75 else RiskTier.HIGH
                trajectory_label = TrajectoryLabel.DECLINING

                # Behavioral decline
                login_count = max(int(10 - w * 1.5 + rng.randint(-1, 1)), 1)
                clicks = max(int(120 - w * 18 + rng.randint(-10, 10)), 12)
                video_pct = max(round(75.0 - w * 12.0 + rng.uniform(-5, 5), 1), 5.0)
                session_mins = max(round(180.0 - w * 25.0 + rng.uniform(-15, 15), 1), 15.0)
                sub_delay = round(1.5 + w * 2.2 + rng.uniform(-1, 2), 1)
                attendance = max(round(88.0 - w * 8.5 + rng.uniform(-3, 3), 1), 35.0)
                ca_mark = max(round(70.0 - w * 8.0 + rng.uniform(-5, 5), 1), 20.0)

                top_drivers = ["declining_logins", "low_video_completion", "late_submissions"]
                if w > 2:
                    top_drivers.append("high_affective_distress")

                aff_weight = 0.40
                beh_weight = 0.35
                acad_weight = 0.25

            elif persona == 1:
                # Moderate Risk / Volatile: fluctuating distress, conceptual confusion
                risk_score = round(0.42 + rng.uniform(-0.12, 0.15), 3)
                risk_tier = RiskTier.MEDIUM
                trajectory_label = rng.choice([TrajectoryLabel.VOLATILE, TrajectoryLabel.DECLINING])

                login_count = rng.randint(4, 9)
                clicks = rng.randint(45, 95)
                video_pct = round(rng.uniform(40.0, 75.0), 1)
                session_mins = round(rng.uniform(60.0, 150.0), 1)
                sub_delay = round(rng.uniform(-0.5, 3.5), 1)
                attendance = round(rng.uniform(65.0, 85.0), 1)
                ca_mark = round(rng.uniform(50.0, 68.0), 1)

                top_drivers = ["conceptual_confusion", "fluctuating_engagement", "erratic_sessions"]
                aff_weight = 0.50
                beh_weight = 0.25
                acad_weight = 0.25

            else:
                # Low Risk / Healthy Performer: consistent and improving
                base_risk = 0.22 - (w / max(num_weeks, 1)) * 0.12
                noise = rng.uniform(-0.04, 0.04)
                risk_score = min(max(round(base_risk + noise, 3), 0.04), 0.35)
                risk_tier = RiskTier.LOW
                trajectory_label = TrajectoryLabel.IMPROVING if w > 1 else TrajectoryLabel.STABLE

                login_count = rng.randint(8, 16)
                clicks = rng.randint(110, 220)
                video_pct = round(rng.uniform(85.0, 99.0), 1)
                session_mins = round(rng.uniform(160.0, 320.0), 1)
                sub_delay = round(rng.uniform(-12.0, -1.0), 1)  # Early submissions
                attendance = round(rng.uniform(90.0, 100.0), 1)
                ca_mark = round(rng.uniform(75.0, 95.0), 1)

                top_drivers = ["regular_logins", "high_video_completion", "early_submissions"]
                aff_weight = 0.20
                beh_weight = 0.40
                acad_weight = 0.40

            # 3a. col.RISK_ASSESSMENTS
            ra_doc = {
                "_id": doc_id,
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "risk_score": risk_score,
                "risk_tier": risk_tier.value if hasattr(risk_tier, "value") else str(risk_tier),
                "modality_contributions": {
                    "affective": aff_weight,
                    "behavioral": beh_weight,
                    "academic": acad_weight,
                },
                "top_drivers": top_drivers,
                "schema_version": 1,
                "source_version": "1.0",
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            ra_ops.append(ReplaceOne({"_id": doc_id}, ra_doc, upsert=True))

            # 3b. col.ENGAGEMENT_TRAJECTORIES
            et_doc = {
                "_id": doc_id,
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "trajectory_label": trajectory_label.value if hasattr(trajectory_label, "value") else str(trajectory_label),
                "confidence": round(rng.uniform(0.78, 0.96), 2),
                "contributing_indicators": top_drivers[:3],
                "schema_version": 1,
                "source_version": "1.0",
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            et_ops.append(ReplaceOne({"_id": doc_id}, et_doc, upsert=True))

            # 3c. col.BEHAVIOR_WEEKLY
            bw_doc = {
                "_id": doc_id,
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "login_count": login_count,
                "session_minutes": session_mins,
                "clicks": clicks,
                "video_play_count": rng.randint(2, 8),
                "video_pause_count": rng.randint(1, 6),
                "video_rewind_count": rng.randint(0, 5),
                "video_skip_count": rng.randint(0, 3),
                "video_completion_pct": video_pct,
                "submissions_count": 1 if w > 0 else 0,
                "avg_submission_delay_hours": sub_delay,
                "schema_version": 1,
                "source_version": "1.0",
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            bw_ops.append(ReplaceOne({"_id": doc_id}, bw_doc, upsert=True))

            # 3d. col.GRADES & col.ATTENDANCE
            grade_doc = {
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
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            grade_ops.append(ReplaceOne({"_id": f"grd_{doc_id}"}, grade_doc, upsert=True))

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
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            att_ops.append(ReplaceOne({"_id": f"att_{doc_id}"}, att_doc, upsert=True))

            # 3e. col.AFFECTIVE_WEEKLY
            distress_map = {
                DistressClass.EXAM_ANXIETY.value: round(rng.uniform(0.1, 0.8), 2),
                DistressClass.CONCEPTUAL_CONFUSION.value: round(rng.uniform(0.15, 0.85), 2),
                DistressClass.ACADEMIC_HELPLESSNESS.value: round(rng.uniform(0.05, 0.6), 2),
                DistressClass.COURSE_FRUSTRATION.value: round(rng.uniform(0.1, 0.7), 2),
                DistressClass.MOTIVATION_EROSION.value: round(rng.uniform(0.1, 0.75), 2),
            }
            stress_tag = "high_stress" if persona == 0 else ("moderate_stress" if persona == 1 else "calm")
            af_doc = {
                "_id": doc_id,
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "emotion_scores": distress_map,
                "stress_label": stress_tag,
                "confidence": round(rng.uniform(0.8, 0.95), 2),
                "message_count": rng.randint(1, 4),
                "top_drivers": [{"token_or_marker": d, "weight": 0.33} for d in top_drivers[:3]],
                "schema_version": 1,
                "source_version": "1.0",
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            af_ops.append(ReplaceOne({"_id": doc_id}, af_doc, upsert=True))

            # 3f. col.MESSAGES
            msg_id = f"msg_{doc_id}"
            sample_clean_texts = [
                "Could anyone explain the recursive edge condition discussed in lecture 4?",
                "Having difficulty setting up the database connection environment locally.",
                "Completed the weekly assignment milestone ahead of schedule.",
                "The lecture explanation on data flow was clear, working on practice quiz now.",
            ]
            msg_doc = {
                "_id": msg_id,
                "message_id": msg_id,
                "pid": pid,
                "course_id": course_id,
                "week_index": w,
                "source_type": SourceType.FORUM.value,
                "clean_text": rng.choice(sample_clean_texts),
                "timestamp": now_utc,
                "response_latency_seconds": float(rng.randint(30, 600)),
                "message_length_chars": 65,
                "message_length_words": 10,
                "schema_version": 1,
                "source_version": "1.0",
                "source": "synthetic",
                "ingested_at": now_utc,
            }
            msg_ops.append(ReplaceOne({"_id": msg_id}, msg_doc, upsert=True))

    # Concurrently write all collections in bulk (reduces ~1,000 round-trips to just 1 parallel call)
    batch_tasks = []
    if vault_ops:
        batch_tasks.append(db[col.IDENTITY_VAULT].bulk_write(vault_ops, ordered=False))
    if enr_ops:
        batch_tasks.append(db[col.ENROLMENTS].bulk_write(enr_ops, ordered=False))
    if ra_ops:
        batch_tasks.append(db[col.RISK_ASSESSMENTS].bulk_write(ra_ops, ordered=False))
    if et_ops:
        batch_tasks.append(db[col.ENGAGEMENT_TRAJECTORIES].bulk_write(et_ops, ordered=False))
    if bw_ops:
        batch_tasks.append(db[col.BEHAVIOR_WEEKLY].bulk_write(bw_ops, ordered=False))
    if grade_ops:
        batch_tasks.append(db[col.GRADES].bulk_write(grade_ops, ordered=False))
    if att_ops:
        batch_tasks.append(db[col.ATTENDANCE].bulk_write(att_ops, ordered=False))
    if af_ops:
        batch_tasks.append(db[col.AFFECTIVE_WEEKLY].bulk_write(af_ops, ordered=False))
    if msg_ops:
        batch_tasks.append(db[col.MESSAGES].bulk_write(msg_ops, ordered=False))

    if batch_tasks:
        await asyncio.gather(*batch_tasks)

    total_ra = len(ra_ops)
    total_et = len(et_ops)
    total_bw = len(bw_ops)
    total_af = len(af_ops)
    total_ac = len(grade_ops)
    total_msg = len(msg_ops)

    # 4. Audit Log Entry
    await log_event(
        request=request,
        db=db,
        action=AuditAction.DATA_IMPORTED,
        actor_id=current_user.id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        target_type="synthetic_data_generator",
        target_id=course_id,
        outcome=AuditOutcome.SUCCESS,
        details={
            "course_id": course_id,
            "num_students": num_students,
            "num_weeks": num_weeks,
            "cohort_profile": profile,
            "risk_assessments_created": total_ra,
            "trajectories_created": total_et,
        },
    )

    return {
        "message": f"Successfully generated synthetic cohort data for {course_id}",
        "course_id": course_id,
        "students_count": num_students,
        "weeks_count": num_weeks,
        "cohort_profile": profile,
        "records_generated": {
            "risk_assessments": total_ra,
            "engagement_trajectories": total_et,
            "behavior_weekly": total_bw,
            "affective_weekly": total_af,
            "academic_records": total_ac,
            "messages": total_msg,
        },
        "sample_students": [
            {"pid": s["pid"], "name": s["name"], "student_id": s["student_id"]}
            for s in created_students[:5]
        ],
    }


# ── Feature 41: Synthetic Data Reset Endpoint ─────────────────────────────────

@router.delete(
    "/synthetic/clear",
    summary="Clear Synthetic Telemetry Data (Feature 41)",
    description="Deletes synthetic data generated for a course to restore baseline state.",
    status_code=status.HTTP_200_OK,
)
async def clear_synthetic_course_data(
    course_id: str = Query(..., description="Target course ID to purge synthetic data for"),
    request: Request = None,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LECTURER)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del_ra, del_et, del_bw, del_af, del_grd, del_att, del_msg = await asyncio.gather(
        db[col.RISK_ASSESSMENTS].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.ENGAGEMENT_TRAJECTORIES].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.BEHAVIOR_WEEKLY].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.AFFECTIVE_WEEKLY].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.GRADES].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.ATTENDANCE].delete_many({"course_id": course_id, "source": "synthetic"}),
        db[col.MESSAGES].delete_many({"course_id": course_id, "source": "synthetic"}),
    )

    if request:
        await log_event(
            request=request,
            db=db,
            action=AuditAction.DATA_EXPORTED,
            actor_id=current_user.id,
            actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            target_type="synthetic_data_clear",
            target_id=course_id,
            outcome=AuditOutcome.SUCCESS,
            details={"course_id": course_id},
        )

    return {
        "message": f"Purged synthetic records for course {course_id}",
        "deleted_counts": {
            "risk_assessments": del_ra.deleted_count,
            "engagement_trajectories": del_et.deleted_count,
            "behavior_weekly": del_bw.deleted_count,
            "affective_weekly": del_af.deleted_count,
            "grades": del_grd.deleted_count,
            "attendance": del_att.deleted_count,
            "messages": del_msg.deleted_count,
        },
    }
