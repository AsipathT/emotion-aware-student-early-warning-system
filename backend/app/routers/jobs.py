import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import require_roles
from app.models.course import Course
from app.models.user import User, UserRole
from app.services.aggregation import compute_weekly_features

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/aggregate-weekly", status_code=status.HTTP_200_OK)
async def trigger_weekly_aggregation(
    request: Request,
    course_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
) -> Dict[str, Any]:
    """
    Manually trigger the weekly aggregation job (Admin only).
    Optionally accepts course_id via query param or json body.
    If the specified course has start_date=None, returns 400 Bad Request.
    """
    target_course_id = course_id
    if target_course_id is None:
        try:
            body = await request.json()
            if isinstance(body, dict) and "course_id" in body and body["course_id"]:
                target_course_id = uuid.UUID(str(body["course_id"]))
        except Exception:
            pass

    if target_course_id:
        c_res = await db.execute(select(Course).where(Course.id == target_course_id))
        course = c_res.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if course.start_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course start_date is not set. Aggregation requires a valid course start date."
            )

    try:
        count = await compute_weekly_features(db, course_id=target_course_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"status": "ok", "records_upserted": count}
