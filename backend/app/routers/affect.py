from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import require_roles
from app.models.analytics import AffectWeekly
from app.models.user import User, UserRole
from app.schemas.analytics import BulkAffectWeeklyCreate
from app.core.pseudonym import resolve_pseudonym


router = APIRouter(prefix="/api/v1/affect", tags=["affect"])


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def bulk_ingest_affect_scores(
    payload: BulkAffectWeeklyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
) -> Dict[str, Any]:
    """
    Admin-only endpoint to bulk-ingest affect weekly scores.
    """
    for record_in in payload.records:
        student_id = await resolve_pseudonym(db, record_in.course_id, record_in.pseudo_student_id)
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown pseudonymous student_id: {record_in.pseudo_student_id}"
            )
            
        stmt = select(AffectWeekly).where(
            AffectWeekly.student_id == student_id,
            AffectWeekly.course_id == record_in.course_id,
            AffectWeekly.week_index == record_in.week_index
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        
        if existing:
            existing.exam_anxiety = record_in.exam_anxiety
            existing.conceptual_confusion = record_in.conceptual_confusion
            existing.academic_helplessness = record_in.academic_helplessness
            existing.course_frustration = record_in.course_frustration
            existing.motivation_erosion = record_in.motivation_erosion
            existing.confidence = record_in.confidence
            existing.message_count = record_in.message_count
            db.add(existing)
        else:
            data = record_in.model_dump(exclude={'pseudo_student_id'})
            data['student_id'] = student_id
            new_record = AffectWeekly(**data)
            db.add(new_record)
            
    await db.flush()
    return {"status": "ingested", "count": len(payload.records)}
