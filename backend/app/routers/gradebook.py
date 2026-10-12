"""
backend/app/routers/gradebook.py

Feature 12: Gradebook Grid, Student View, Manual Entries, and CSV Export.
Operates strictly on 'lms_gradebook'.
"""

import io
import csv
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.schema_mapping import (
    CANONICAL_COURSES,
    CANONICAL_USERS,
    COL_GRADEBOOK,
    check_course_ownership,
)
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/v1/courses", tags=["gradebook"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ManualGradeEntryIn(BaseModel):
    student_id: Union[uuid.UUID, str]
    title: str = Field(..., max_length=255)
    score: float = Field(..., ge=0)
    max_score: float = Field(..., gt=0)
    weight: float = Field(default=1.0, ge=0)


def compute_student_summary(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes weighted total and score_so_far percentage."""
    if not entries:
        return {"weighted_total": 0.0, "score_so_far": 0.0, "entries": []}

    total_weighted_points = 0.0
    total_weights = 0.0

    for e in entries:
        score = float(e.get("score", 0.0))
        max_score = float(e.get("max_score", 100.0)) or 100.0
        weight = float(e.get("weight", 1.0))

        percentage = score / max_score
        total_weighted_points += percentage * weight
        total_weights += weight

    score_so_far = round((total_weighted_points / total_weights) * 100.0, 2) if total_weights > 0 else 0.0
    weighted_total = round(total_weighted_points, 2)

    return {
        "weighted_total": weighted_total,
        "score_so_far": score_so_far,
        "entries": entries,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{course_id}/gradebook")
async def get_course_gradebook(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR)),
) -> Dict[str, Any]:
    """
    Gradebook grid for a course (students x items with scores, weighted total per student).
    Counsellor is read-only; Lecturer must own the course; Admin has full access.
    """
    cid_str = str(course_id)
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Check course existence & ownership
    course_doc = (
        await db[CANONICAL_COURSES].find_one({"_id": cid_str})
        or await db[CANONICAL_COURSES].find_one({"id": cid_str})
        or await db[CANONICAL_COURSES].find_one({"course_id": cid_str})
    )
    if not course_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if role_val == "lecturer":
        if str(course_doc.get("lecturer_id")) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the course instructor.")

    # Retrieve all gradebook entries for this course
    cursor = db[COL_GRADEBOOK].find({"course_id": cid_str})
    all_entries = await cursor.to_list(length=5000)

    # Group entries by student_id
    students_map: Dict[str, List[Dict[str, Any]]] = {}
    distinct_items: Dict[str, Dict[str, Any]] = {}

    for entry in all_entries:
        entry["id"] = entry.pop("_id")
        sid = str(entry["student_id"])
        item_key = f"{entry.get('item_type')}:{entry.get('item_id') or entry.get('title')}"
        if item_key not in distinct_items:
            distinct_items[item_key] = {
                "key": item_key,
                "title": entry.get("title"),
                "item_type": entry.get("item_type"),
                "max_score": entry.get("max_score"),
                "weight": entry.get("weight"),
            }
        students_map.setdefault(sid, []).append(entry)

    # Fetch student profiles/names for display
    student_ids = list(students_map.keys())
    user_docs = await db[CANONICAL_USERS].find({"_id": {"$in": student_ids}}).to_list(length=1000)
    users_by_id = {str(u["_id"]): u for u in user_docs}

    students_grid = []
    for sid, s_entries in students_map.items():
        user_info = users_by_id.get(sid, {})
        summary = compute_student_summary(s_entries)
        students_grid.append({
            "student_id": sid,
            "full_name": user_info.get("full_name", f"Student {sid[:8]}"),
            "email": user_info.get("email", ""),
            "weighted_total": summary["weighted_total"],
            "score_so_far": summary["score_so_far"],
            "entries": summary["entries"],
        })

    return {
        "course_id": cid_str,
        "items": list(distinct_items.values()),
        "students": students_grid,
    }


@router.get("/{course_id}/gradebook/me")
async def get_my_gradebook(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Dict[str, Any]:
    """Student own gradebook view: only own entries, weighted total, and score_so_far."""
    cid_str = str(course_id)
    uid_str = str(current_user.id)

    cursor = db[COL_GRADEBOOK].find({"course_id": cid_str, "student_id": uid_str})
    entries = await cursor.to_list(length=500)
    for e in entries:
        e["id"] = e.pop("_id")

    summary = compute_student_summary(entries)
    return {
        "course_id": cid_str,
        "student_id": uid_str,
        **summary,
    }


@router.post("/{course_id}/gradebook/manual", status_code=status.HTTP_201_CREATED)
async def add_manual_grade(
    course_id: str,
    body: ManualGradeEntryIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """
    Manual grade entry by lecturer or admin.
    Counsellors are rejected with 403.
    Upserts into lms_gradebook.
    """
    cid_str = str(course_id)
    sid_str = str(body.student_id)
    await check_course_ownership(db, cid_str, current_user)

    now = datetime.now(timezone.utc)
    entry_id = str(uuid.uuid4())

    entry_doc = {
        "_id": entry_id,
        "id": entry_id,
        "course_id": cid_str,
        "student_id": sid_str,
        "item_type": "manual",
        "item_id": entry_id,
        "title": body.title,
        "score": body.score,
        "max_score": body.max_score,
        "weight": body.weight,
        "recorded_at": now,
        "created_at": now,
        "updated_at": now,
    }

    await db[COL_GRADEBOOK].insert_one(entry_doc)
    return entry_doc


@router.get("/{course_id}/gradebook/csv")
async def export_gradebook_csv(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Response:
    """CSV download for lecturer or admin only."""
    cid_str = str(course_id)
    await check_course_ownership(db, cid_str, current_user)

    cursor = db[COL_GRADEBOOK].find({"course_id": cid_str})
    entries = await cursor.to_list(length=5000)

    # Fetch users for student name mapping
    student_ids = list({str(e["student_id"]) for e in entries})
    user_docs = await db[CANONICAL_USERS].find({"_id": {"$in": student_ids}}).to_list(length=1000)
    users_by_id = {str(u["_id"]): u.get("full_name", "") for u in user_docs}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Student ID",
        "Student Name",
        "Item Type",
        "Item Title",
        "Score",
        "Max Score",
        "Weight",
        "Recorded At",
    ])

    for e in entries:
        sid = str(e.get("student_id"))
        sname = users_by_id.get(sid, sid)
        writer.writerow([
            sid,
            sname,
            e.get("item_type", ""),
            e.get("title", ""),
            e.get("score", 0),
            e.get("max_score", 0),
            e.get("weight", 1.0),
            str(e.get("recorded_at", "")),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gradebook_{cid_str}.csv"},
    )
