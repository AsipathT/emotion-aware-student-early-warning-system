import io
import csv
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.course import Course
from app.models.gradebook import GradebookEntry
from app.models.user import User
from app.schemas.gradebook import GradebookEntryCreate, GradebookEntryResponse


router = APIRouter(prefix="/api/v1/courses", tags=["gradebook"])


@router.get("/{course_id}/gradebook", response_model=List[GradebookEntryResponse])
async def get_gradebook_grid(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin", "counsellor"))
):
    stmt = select(GradebookEntry).where(GradebookEntry.course_id == course_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{course_id}/gradebook/me", response_model=List[GradebookEntryResponse])
async def get_my_grades(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    stmt = select(GradebookEntry).where(
        GradebookEntry.course_id == course_id,
        GradebookEntry.student_id == current_user.id
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{course_id}/gradebook", response_model=GradebookEntryResponse)
async def add_manual_grade(
    course_id: uuid.UUID,
    entry_in: GradebookEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    entry = GradebookEntry(course_id=course_id, **entry_in.model_dump())
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.get("/{course_id}/gradebook/csv")
async def download_gradebook_csv(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    stmt = select(GradebookEntry).where(GradebookEntry.course_id == course_id)
    result = await db.execute(stmt)
    entries = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "student_id", "item_type", "title", "score", "max_score", "weight", "recorded_at"])
    
    for entry in entries:
        writer.writerow([
            str(entry.id),
            str(entry.student_id),
            entry.item_type,
            entry.title,
            entry.score,
            entry.max_score,
            entry.weight,
            entry.recorded_at.isoformat()
        ])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gradebook_{course_id}.csv"}
    )
