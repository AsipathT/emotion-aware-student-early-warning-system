import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.course import Course
from app.models.user import User
from app.schemas.attendance import (
    AttendanceRecordResponse, AttendanceSessionCreate,
    AttendanceSessionResponse, BulkAttendanceMark
)


router = APIRouter(prefix="/api/v1/courses", tags=["attendance"])


@router.post("/{course_id}/attendance/sessions", response_model=AttendanceSessionResponse)
async def create_attendance_session(
    course_id: uuid.UUID,
    session_in: AttendanceSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    session = AttendanceSession(
        course_id=course_id,
        created_by=current_user.id,
        **session_in.model_dump()
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.get("/{course_id}/attendance/sessions", response_model=List[AttendanceSessionResponse])
async def list_attendance_sessions(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(AttendanceSession).where(AttendanceSession.course_id == course_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{course_id}/attendance/sessions/{session_id}/records", response_model=List[AttendanceRecordResponse])
async def bulk_mark_attendance(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: BulkAttendanceMark,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    session = await db.get(AttendanceSession, session_id)
    if not session or session.course_id != course_id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    records = []
    for rec_in in payload.records:
        # Check if exists
        stmt = select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == rec_in.student_id
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.status = rec_in.status
            existing.marked_by = current_user.id
            db.add(existing)
            records.append(existing)
        else:
            record = AttendanceRecord(
                session_id=session_id,
                student_id=rec_in.student_id,
                status=rec_in.status,
                marked_by=current_user.id
            )
            db.add(record)
            records.append(record)
            
    await db.flush()
    # refresh all
    for r in records:
        await db.refresh(r)
        
    return records


@router.get("/{course_id}/attendance/sessions/{session_id}/records", response_model=List[AttendanceRecordResponse])
async def get_session_records(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    session = await db.get(AttendanceSession, session_id)
    if not session or session.course_id != course_id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    stmt = select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{course_id}/attendance/me", response_model=List[AttendanceRecordResponse])
async def get_my_attendance(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    stmt = (
        select(AttendanceRecord)
        .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        .where(AttendanceSession.course_id == course_id)
        .where(AttendanceRecord.student_id == current_user.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
