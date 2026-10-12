"""
backend/app/routers/attendance.py

Feature 13: Attendance Sessions, Bulk Marking, Student Rate, and Summary.
Operates strictly on 'lms_*' collections:
  - lms_attendance_sessions
  - lms_attendance_records
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.schema_mapping import (
    CANONICAL_COURSES,
    CANONICAL_USERS,
    COL_ATTENDANCE_RECORDS,
    COL_ATTENDANCE_SESSIONS,
    check_course_ownership,
    check_student_enrolled,
)
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/v1/courses", tags=["attendance"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AttendanceSessionCreateIn(BaseModel):
    title: str = Field(..., max_length=255)
    session_date: datetime


class AttendanceRecordItem(BaseModel):
    student_id: str
    status: str = Field(..., pattern="^(present|late|absent|excused)$")


class BulkAttendanceMarkIn(BaseModel):
    records: List[AttendanceRecordItem]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{course_id}/attendance/sessions", status_code=status.HTTP_201_CREATED)
async def create_attendance_session(
    course_id: str,
    body: AttendanceSessionCreateIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """Lecturer (course owner) or admin creates an attendance session."""
    cid_str = str(course_id)
    await check_course_ownership(db, cid_str, current_user)

    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    session_doc = {
        "_id": sid,
        "id": sid,
        "course_id": cid_str,
        "title": body.title,
        "session_date": body.session_date,
        "created_by": str(current_user.id),
        "created_at": now,
        "updated_at": now,
    }

    await db[COL_ATTENDANCE_SESSIONS].insert_one(session_doc)
    return session_doc


@router.get("/{course_id}/attendance/sessions")
async def list_attendance_sessions(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR)),
) -> List[Dict[str, Any]]:
    """Lists attendance sessions for a course."""
    cid_str = str(course_id)
    cursor = db[COL_ATTENDANCE_SESSIONS].find({"course_id": cid_str}).sort("session_date", 1)
    docs = await cursor.to_list(length=1000)
    for d in docs:
        d["id"] = d.pop("_id")
    return docs


@router.post("/{course_id}/attendance/sessions/{session_id}/records")
async def bulk_mark_attendance(
    course_id: str,
    session_id: str,
    body: BulkAttendanceMarkIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """
    Bulk marks attendance for a session.
    Enforces that students must be enrolled in the course.
    Re-marking updates the existing record (idempotent, no duplicates).
    Counsellors cannot write.
    """
    cid_str = str(course_id)
    sess_id_str = str(session_id)
    await check_course_ownership(db, cid_str, current_user)

    session_doc = await db[COL_ATTENDANCE_SESSIONS].find_one({"_id": sess_id_str, "course_id": cid_str})
    if not session_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")

    now = datetime.now(timezone.utc)
    updated_records = []

    for item in body.records:
        sid_str = str(item.student_id)

        # Check student enrollment
        student_user = await db[CANONICAL_USERS].find_one({"_id": sid_str}) or {"_id": sid_str, "id": sid_str}
        is_enrolled = await check_student_enrolled(db, cid_str, student_user)
        if not is_enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Student {sid_str} is not enrolled in this course.",
            )

        filter_q = {"session_id": sess_id_str, "student_id": sid_str}
        existing = await db[COL_ATTENDANCE_RECORDS].find_one(filter_q)

        if existing:
            await db[COL_ATTENDANCE_RECORDS].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "status": item.status,
                        "marked_by": str(current_user.id),
                        "marked_at": now,
                        "updated_at": now,
                    }
                },
            )
            updated_records.append({**existing, "status": item.status, "updated_at": now})
        else:
            rec_id = str(uuid.uuid4())
            new_rec = {
                "_id": rec_id,
                "id": rec_id,
                "session_id": sess_id_str,
                "course_id": cid_str,
                "student_id": sid_str,
                "status": item.status,
                "marked_by": str(current_user.id),
                "marked_at": now,
                "created_at": now,
                "updated_at": now,
            }
            await db[COL_ATTENDANCE_RECORDS].insert_one(new_rec)
            updated_records.append(new_rec)

    return {
        "session_id": sess_id_str,
        "records_count": len(updated_records),
        "status": "success",
    }


@router.get("/{course_id}/attendance/me")
async def get_my_attendance(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Dict[str, Any]:
    """Student reads only their own attendance records and computed attendance rate."""
    cid_str = str(course_id)
    uid_str = str(current_user.id)

    total_sessions = await db[COL_ATTENDANCE_SESSIONS].count_documents({"course_id": cid_str})
    cursor = db[COL_ATTENDANCE_RECORDS].find({"course_id": cid_str, "student_id": uid_str})
    records = await cursor.to_list(length=500)

    for r in records:
        r["id"] = r.pop("_id")

    attended_count = sum(1 for r in records if r.get("status") in ("present", "late"))
    rate = round((attended_count / total_sessions) * 100.0, 2) if total_sessions > 0 else 100.0

    return {
        "course_id": cid_str,
        "student_id": uid_str,
        "total_sessions": total_sessions,
        "attended_sessions": attended_count,
        "attendance_rate": rate,
        "records": records,
    }


@router.get("/{course_id}/attendance/summary")
async def get_course_attendance_summary(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR)),
) -> Dict[str, Any]:
    """Lecturer, admin, or counsellor reads course attendance summary."""
    cid_str = str(course_id)

    sessions_cursor = db[COL_ATTENDANCE_SESSIONS].find({"course_id": cid_str})
    sessions = await sessions_cursor.to_list(length=1000)
    for s in sessions:
        s["id"] = s.pop("_id")

    records_cursor = db[COL_ATTENDANCE_RECORDS].find({"course_id": cid_str})
    records = await records_cursor.to_list(length=5000)
    for r in records:
        r["id"] = r.pop("_id")

    # Group by student
    student_records_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        student_records_map.setdefault(str(r["student_id"]), []).append(r)

    total_sessions = len(sessions)
    student_summaries = []

    # Fetch user names
    student_ids = list(student_records_map.keys())
    user_docs = await db[CANONICAL_USERS].find({"_id": {"$in": student_ids}}).to_list(length=1000)
    users_by_id = {str(u["_id"]): u for u in user_docs}

    for sid, recs in student_records_map.items():
        attended = sum(1 for r in recs if r.get("status") in ("present", "late"))
        rate = round((attended / total_sessions) * 100.0, 2) if total_sessions > 0 else 100.0
        u_info = users_by_id.get(sid, {})
        student_summaries.append({
            "student_id": sid,
            "full_name": u_info.get("full_name", f"Student {sid[:8]}"),
            "email": u_info.get("email", ""),
            "attended_sessions": attended,
            "total_sessions": total_sessions,
            "attendance_rate": rate,
        })

    avg_rate = (
        round(sum(s["attendance_rate"] for s in student_summaries) / len(student_summaries), 2)
        if student_summaries
        else 100.0
    )

    return {
        "course_id": cid_str,
        "total_sessions": total_sessions,
        "average_attendance_rate": avg_rate,
        "sessions": sessions,
        "students": student_summaries,
    }
