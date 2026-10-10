import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.assessment import Assignment, AssignmentSubmission
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssignmentCreate, AssignmentResponse, AssignmentSubmissionCreate,
    AssignmentSubmissionGrade, AssignmentSubmissionResponse, AssignmentUpdate
)

router = APIRouter(prefix="/api/v1/courses", tags=["assignments"])


@router.post("/{course_id}/assignments", response_model=AssignmentResponse)
async def create_assignment(
    course_id: uuid.UUID,
    assignment_in: AssignmentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN))
):
    cid_str = str(course_id)
    course = await db.courses.find_one({"_id": cid_str})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    assignment = Assignment(course_id=course_id, **assignment_in.model_dump())
    await db.assignments.insert_one(assignment.to_mongo())
    
    return assignment.model_dump()


@router.get("/{course_id}/assignments", response_model=List[AssignmentResponse])
async def list_assignments(
    course_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cid_str = str(course_id)
    filter_q = {"course_id": cid_str}
    
    if current_user.role == UserRole.STUDENT:
        filter_q["is_published"] = True
    
    cursor = db.assignments.find(filter_q)
    docs = await cursor.to_list(length=1000)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs


@router.get("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    aid_str = str(assignment_id)
    doc = await db.assignments.find_one({"_id": aid_str})
    if not doc or doc.get("course_id") != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if current_user.role == UserRole.STUDENT and not doc.get("is_published"):
        raise HTTPException(status_code=403, detail="Assignment not published")
        
    doc["id"] = doc.pop("_id")
    return doc


@router.patch("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    assignment_in: AssignmentUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN))
):
    aid_str = str(assignment_id)
    doc = await db.assignments.find_one({"_id": aid_str})
    if not doc or doc.get("course_id") != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    update_data = assignment_in.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db.assignments.update_one({"_id": aid_str}, {"$set": update_data})
        
    doc = await db.assignments.find_one({"_id": aid_str})
    doc["id"] = doc.pop("_id")
    return doc


@router.delete("/{course_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN))
):
    aid_str = str(assignment_id)
    doc = await db.assignments.find_one({"_id": aid_str})
    if not doc or doc.get("course_id") != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    await db.assignments.delete_one({"_id": aid_str})
    return None


@router.post("/{course_id}/assignments/{assignment_id}/submit", response_model=AssignmentSubmissionResponse)
async def submit_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_in: AssignmentSubmissionCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT))
):
    aid_str = str(assignment_id)
    assignment = await db.assignments.find_one({"_id": aid_str})
    if not assignment or assignment.get("course_id") != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if not assignment.get("is_published"):
        raise HTTPException(status_code=403, detail="Assignment not published")

    existing = await db.assignment_submissions.find_one({
        "assignment_id": aid_str,
        "student_id": str(current_user.id)
    })
    if existing:
        raise HTTPException(status_code=409, detail="Assignment already submitted")

    submission = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        **submission_in.model_dump()
    )
    await db.assignment_submissions.insert_one(submission.to_mongo())
    res = submission.model_dump()
    return res


@router.get("/{course_id}/assignments/{assignment_id}/submissions", response_model=List[AssignmentSubmissionResponse])
async def list_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN))
):
    cursor = db.assignment_submissions.find({"assignment_id": str(assignment_id)})
    docs = await cursor.to_list(length=1000)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs


@router.post("/{course_id}/assignments/{assignment_id}/submissions/{student_id}/grade", response_model=AssignmentSubmissionResponse)
async def grade_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    grade_in: AssignmentSubmissionGrade,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN))
):
    aid_str = str(assignment_id)
    sid_str = str(student_id)
    
    submission = await db.assignment_submissions.find_one({
        "assignment_id": aid_str,
        "student_id": sid_str
    })
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = await db.assignments.find_one({"_id": aid_str})
    if not assignment or assignment.get("course_id") != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")

    update_data = {
        "score": grade_in.score,
        "feedback": grade_in.feedback,
        "graded_by": str(current_user.id),
        "graded_at": datetime.now(timezone.utc)
    }
    await db.assignment_submissions.update_one({"_id": submission["_id"]}, {"$set": update_data})
    
    # Upsert GradebookEntry for this assignment + student
    gb_filter = {
        "course_id": str(course_id),
        "student_id": sid_str,
        "item_type": "assignment",
        "item_id": aid_str
    }
    
    gb_entry = await db.gradebook_entries.find_one(gb_filter)
    if gb_entry:
        await db.gradebook_entries.update_one(
            {"_id": gb_entry["_id"]},
            {"$set": {
                "score": grade_in.score,
                "max_score": assignment.get("max_score"),
                "weight": assignment.get("weight"),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
    else:
        new_gb_entry = GradebookEntry(
            course_id=course_id,
            student_id=student_id,
            item_type="assignment",
            item_id=assignment_id,
            title=assignment.get("title", ""),
            score=grade_in.score,
            max_score=assignment.get("max_score", 100),
            weight=assignment.get("weight", 1.0)
        )
        await db.gradebook_entries.insert_one(new_gb_entry.to_mongo())

    submission = await db.assignment_submissions.find_one({"_id": submission["_id"]})
    submission["id"] = submission.pop("_id")
    return submission
