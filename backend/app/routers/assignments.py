"""
backend/app/routers/assignments.py

Feature 10: Assignment Management and Grading.
Operates strictly on 'lms_*' collections:
  - lms_assignments
  - lms_submissions
  - lms_gradebook
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.schema_mapping import (
    COL_ASSIGNMENTS,
    COL_GRADEBOOK,
    COL_SUBMISSIONS,
    check_course_ownership,
    check_student_enrolled,
)
from app.models.assessment import Assignment, AssignmentSubmission
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentSubmissionCreate,
    AssignmentSubmissionGrade,
    AssignmentSubmissionResponse,
    AssignmentUpdate,
)

router = APIRouter(prefix="/api/v1/courses", tags=["assignments"])


@router.post("/{course_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    course_id: uuid.UUID,
    assignment_in: AssignmentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """Create an assignment (course instructor or admin only)."""
    cid_str = str(course_id)
    await check_course_ownership(db, cid_str, current_user)

    assignment = Assignment(course_id=course_id, **assignment_in.model_dump())
    await db[COL_ASSIGNMENTS].insert_one(assignment.to_mongo())
    return assignment.model_dump()


@router.get("/{course_id}/assignments", response_model=List[AssignmentResponse])
async def list_assignments(
    course_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List assignments for a course. Students only see published ones."""
    cid_str = str(course_id)
    filter_q: Dict[str, Any] = {"course_id": cid_str}

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val == "student":
        filter_q["is_published"] = True

    cursor = db[COL_ASSIGNMENTS].find(filter_q)
    docs = await cursor.to_list(length=1000)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs


@router.get("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get single assignment details."""
    aid_str = str(assignment_id)
    doc = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str})
    if not doc or doc.get("course_id") != str(course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val == "student" and not doc.get("is_published"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assignment not published")

    doc["id"] = doc.pop("_id")
    return doc


@router.patch("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    assignment_in: AssignmentUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """Update assignment (course owner only)."""
    cid_str = str(course_id)
    aid_str = str(assignment_id)
    await check_course_ownership(db, cid_str, current_user)

    doc = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str, "course_id": cid_str})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    update_data = assignment_in.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db[COL_ASSIGNMENTS].update_one({"_id": aid_str}, {"$set": update_data})

    updated = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str})
    updated["id"] = updated.pop("_id")
    return updated


@router.delete("/{course_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> None:
    """Delete assignment (course owner only)."""
    cid_str = str(course_id)
    aid_str = str(assignment_id)
    await check_course_ownership(db, cid_str, current_user)

    doc = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str, "course_id": cid_str})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    await db[COL_ASSIGNMENTS].delete_one({"_id": aid_str})
    return None


@router.post("/{course_id}/assignments/{assignment_id}/submit", response_model=AssignmentSubmissionResponse)
async def submit_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_in: AssignmentSubmissionCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Dict[str, Any]:
    """
    Student submits an assignment.
    Validates enrollment. Computes is_late and delay_days.
    Resubmission policy: Allowed before grading (updates submission); forbidden after grading.
    """
    cid_str = str(course_id)
    aid_str = str(assignment_id)
    uid_str = str(current_user.id)

    assignment = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str, "course_id": cid_str})
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if not assignment.get("is_published"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assignment not published")

    is_enrolled = await check_student_enrolled(db, cid_str, current_user)
    if not is_enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course")

    existing = await db[COL_SUBMISSIONS].find_one({
        "assignment_id": aid_str,
        "student_id": uid_str,
    })
    if existing and existing.get("score") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already graded; resubmission is not permitted.",
        )

    now = datetime.now(timezone.utc)
    is_late = False
    delay_days = 0
    due_at = assignment.get("due_at")
    if due_at:
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if now > due_at:
            is_late = True
            delay_days = max(1, (now - due_at).days)

    if existing:
        update_fields = {
            "content_text": submission_in.content_text,
            "file_url": submission_in.file_url,
            "submitted_at": now,
            "is_late": is_late,
            "delay_days": delay_days,
            "updated_at": now,
        }
        await db[COL_SUBMISSIONS].update_one({"_id": existing["_id"]}, {"$set": update_fields})
        updated = await db[COL_SUBMISSIONS].find_one({"_id": existing["_id"]})
        updated["id"] = updated.pop("_id")
        return updated

    submission = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        is_late=is_late,
        delay_days=delay_days,
        **submission_in.model_dump(),
    )
    await db[COL_SUBMISSIONS].insert_one(submission.to_mongo())
    return submission.model_dump()


@router.get("/{course_id}/assignments/{assignment_id}/my-submission", response_model=Optional[AssignmentSubmissionResponse])
async def get_my_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Optional[Dict[str, Any]]:
    """Student reads only their own submission."""
    aid_str = str(assignment_id)
    uid_str = str(current_user.id)
    doc = await db[COL_SUBMISSIONS].find_one({"assignment_id": aid_str, "student_id": uid_str})
    if not doc:
        return None
    doc["id"] = doc.pop("_id")
    return doc


@router.get("/{course_id}/assignments/{assignment_id}/submissions", response_model=List[AssignmentSubmissionResponse])
async def list_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> List[Dict[str, Any]]:
    """Lecturer lists submissions for an assignment (course instructor or admin only)."""
    cid_str = str(course_id)
    await check_course_ownership(db, cid_str, current_user)

    cursor = db[COL_SUBMISSIONS].find({"assignment_id": str(assignment_id)})
    docs = await cursor.to_list(length=1000)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs


@router.post(
    "/{course_id}/assignments/{assignment_id}/submissions/{student_id}/grade",
    response_model=AssignmentSubmissionResponse,
)
async def grade_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    grade_in: AssignmentSubmissionGrade,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """
    Grade a submission and upsert a gradebook entry.
    Course instructor or admin only. Score cannot exceed assignment max_score.
    """
    cid_str = str(course_id)
    aid_str = str(assignment_id)
    sid_str = str(student_id)

    await check_course_ownership(db, cid_str, current_user)

    assignment = await db[COL_ASSIGNMENTS].find_one({"_id": aid_str, "course_id": cid_str})
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    max_score = float(assignment.get("max_score", 100.0))
    if grade_in.score > max_score:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score {grade_in.score} exceeds maximum allowed score of {max_score}.",
        )

    submission = await db[COL_SUBMISSIONS].find_one({
        "assignment_id": aid_str,
        "student_id": sid_str,
    })
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    now = datetime.now(timezone.utc)
    update_data = {
        "score": grade_in.score,
        "feedback": grade_in.feedback,
        "graded_by": str(current_user.id),
        "graded_at": now,
        "updated_at": now,
    }
    await db[COL_SUBMISSIONS].update_one({"_id": submission["_id"]}, {"$set": update_data})

    # Upsert lms_gradebook document (item_type: 'assignment')
    gb_filter = {
        "course_id": cid_str,
        "student_id": sid_str,
        "item_type": "assignment",
        "item_id": aid_str,
    }

    gb_entry = await db[COL_GRADEBOOK].find_one(gb_filter)
    if gb_entry:
        await db[COL_GRADEBOOK].update_one(
            {"_id": gb_entry["_id"]},
            {
                "$set": {
                    "score": grade_in.score,
                    "max_score": max_score,
                    "weight": float(assignment.get("weight", 1.0)),
                    "recorded_at": now,
                    "updated_at": now,
                }
            },
        )
    else:
        new_gb_entry = GradebookEntry(
            course_id=course_id,
            student_id=student_id,
            item_type="assignment",
            item_id=assignment_id,
            title=assignment.get("title", "Assignment"),
            score=grade_in.score,
            max_score=max_score,
            weight=float(assignment.get("weight", 1.0)),
            recorded_at=now,
        )
        await db[COL_GRADEBOOK].insert_one(new_gb_entry.to_mongo())

    updated_sub = await db[COL_SUBMISSIONS].find_one({"_id": submission["_id"]})
    updated_sub["id"] = updated_sub.pop("_id")
    return updated_sub
