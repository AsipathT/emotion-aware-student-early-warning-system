from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import require_roles
from app.models.analytics import AffectWeekly
from app.models.user import User
from app.schemas.analytics import BulkAffectWeeklyCreate


router = APIRouter(prefix="/api/v1/affect", tags=["affect"])


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def bulk_ingest_affect_scores(
    payload: BulkAffectWeeklyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
) -> Dict[str, Any]:
    """
    Admin-only endpoint to bulk-ingest affect weekly scores.
    """
    for record_in in payload.records:
        # Check if exists
        stmt = select(AffectWeekly).where(
            AffectWeekly.student_id == record_in.student_id,
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
            new_record = AffectWeekly(**record_in.model_dump())
            db.add(new_record)
            
    await db.flush()
    return {"status": "ingested", "count": len(payload.records)}
