import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.assessment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.user import User
from app.schemas.assessment import (
    AssignmentCreate, AssignmentResponse, AssignmentSubmissionCreate,
    AssignmentSubmissionGrade, AssignmentSubmissionResponse, AssignmentUpdate
)


router = APIRouter(prefix="/api/v1/courses", tags=["assignments"])


@router.post("/{course_id}/assignments", response_model=AssignmentResponse)
async def create_assignment(
    course_id: uuid.UUID,
    assignment_in: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    assignment = Assignment(course_id=course_id, **assignment_in.model_dump())
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@router.get("/{course_id}/assignments", response_model=List[AssignmentResponse])
async def list_assignments(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Assignment).where(Assignment.course_id == course_id)
    if current_user.role == "student":
        stmt = stmt.where(Assignment.is_published == True)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if current_user.role == "student" and not assignment.is_published:
        raise HTTPException(status_code=403, detail="Assignment not published")
        
    return assignment


@router.patch("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    assignment_in: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    update_data = assignment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)
        
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@router.delete("/{course_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    await db.delete(assignment)
    return None


@router.post("/{course_id}/assignments/{assignment_id}/submit", response_model=AssignmentSubmissionResponse)
async def submit_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_in: AssignmentSubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if not assignment.is_published:
        raise HTTPException(status_code=403, detail="Assignment not published")

    # Check for existing submission
    stmt = select(AssignmentSubmission).where(
        AssignmentSubmission.assignment_id == assignment_id,
        AssignmentSubmission.student_id == current_user.id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Assignment already submitted")

    submission = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        **submission_in.model_dump()
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return submission


@router.get("/{course_id}/assignments/{assignment_id}/submissions", response_model=List[AssignmentSubmissionResponse])
async def list_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    stmt = select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{course_id}/assignments/{assignment_id}/submissions/{student_id}/grade", response_model=AssignmentSubmissionResponse)
async def grade_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    grade_in: AssignmentSubmissionGrade,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    stmt = select(AssignmentSubmission).where(
        AssignmentSubmission.assignment_id == assignment_id,
        AssignmentSubmission.student_id == student_id
    )
    result = await db.execute(stmt)
    submission = result.scalar_one_or_none()
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = await db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")

    submission.score = grade_in.score
    submission.feedback = grade_in.feedback
    submission.graded_by = current_user.id
    from datetime import datetime, timezone
    submission.graded_at = datetime.now(timezone.utc)
    
    db.add(submission)
    await db.flush()

    # Upsert GradebookEntry for this assignment + student
    from app.models.gradebook import GradebookEntry
    gb_stmt = select(GradebookEntry).where(
        GradebookEntry.course_id == course_id,
        GradebookEntry.student_id == student_id,
        GradebookEntry.item_type == "assignment",
        GradebookEntry.item_id == assignment_id
    )
    gb_result = await db.execute(gb_stmt)
    gb_entry = gb_result.scalar_one_or_none()

    if gb_entry:
        gb_entry.score = grade_in.score
        gb_entry.max_score = assignment.max_score
        gb_entry.weight = assignment.weight
    else:
        gb_entry = GradebookEntry(
            course_id=course_id,
            student_id=student_id,
            item_type="assignment",
            item_id=assignment_id,
            title=assignment.title,
            score=grade_in.score,
            max_score=assignment.max_score,
            weight=assignment.weight,
        )
        db.add(gb_entry)

    await db.flush()
    await db.refresh(submission)
    return submission
