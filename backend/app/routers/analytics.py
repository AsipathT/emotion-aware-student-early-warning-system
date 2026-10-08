import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.analytics import RiskScore, TrajectoryLabel, WeeklyFeature
from app.models.user import User
from app.schemas.analytics import RiskScoreResponse, TrajectoryLabelResponse, WeeklyFeatureResponse


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin", "counsellor"))
):
    """
    Returns high-level summary metrics for the dashboard (mocked for now,
    but reads from actual tables where possible).
    """
    stmt = select(RiskScore).order_by(RiskScore.created_at.desc()).limit(100)
    res = await db.execute(stmt)
    recent_risks = res.scalars().all()
    
    high_risk_count = sum(1 for r in recent_risks if r.risk_tier == "High")
    
    return {
        "active_alerts": high_risk_count,
        "recent_risk_scores": [{"student_id": r.student_id, "score": r.risk_score, "tier": r.risk_tier} for r in recent_risks[:10]]
    }


@router.get("/courses/{course_id}/risk", response_model=List[RiskScoreResponse])
async def get_course_risk(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin", "counsellor"))
):
    stmt = select(RiskScore).where(RiskScore.course_id == course_id).order_by(RiskScore.week_index.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/students/{student_id}/trajectory", response_model=List[TrajectoryLabelResponse])
async def get_student_trajectory(
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin", "counsellor"))
):
    stmt = select(TrajectoryLabel).where(
        TrajectoryLabel.student_id == student_id,
        TrajectoryLabel.course_id == course_id
    ).order_by(TrajectoryLabel.week_index)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/courses/{course_id}/synthetic", status_code=status.HTTP_201_CREATED)
async def generate_synthetic(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    from app.services.synthetic import generate_synthetic_data
    await generate_synthetic_data(db, str(course_id))
    await db.commit()
    return {"status": "generated"}


@router.get("/courses/{course_id}/export")
async def export_data(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    from fastapi.responses import StreamingResponse
    from app.services.export import export_training_data
    
    csv_data = await export_training_data(db, str(course_id))
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=training_data_{course_id}.csv"}
    )

