import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.analytics import RiskScore, TrajectoryLabel, WeeklyFeature
from app.models.user import User, UserRole
from app.schemas.analytics import (
    RiskScoreResponse, TrajectoryLabelResponse, WeeklyFeatureResponse,
    RiskScoreCreate, TrajectoryLabelCreate
)
from app.core.pseudonym import resolve_pseudonym


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.post("/ingest/risk", status_code=status.HTTP_201_CREATED)
async def ingest_risk_scores(
    payload: List[RiskScoreCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
) -> Dict[str, Any]:
    count = 0
    for record_in in payload:
        student_id = await resolve_pseudonym(db, record_in.course_id, record_in.pseudo_student_id)
        if not student_id:
            continue
        
        stmt = select(RiskScore).where(
            RiskScore.student_id == student_id,
            RiskScore.course_id == record_in.course_id,
            RiskScore.week_index == record_in.week_index
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        
        data = record_in.model_dump(exclude={'pseudo_student_id'})
        data['student_id'] = student_id
        
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            db.add(existing)
        else:
            db.add(RiskScore(**data))
        count += 1
            
    await db.commit()
    return {"status": "ingested", "count": count}


@router.post("/ingest/trajectory", status_code=status.HTTP_201_CREATED)
async def ingest_trajectory_labels(
    payload: List[TrajectoryLabelCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
) -> Dict[str, Any]:
    count = 0
    for record_in in payload:
        student_id = await resolve_pseudonym(db, record_in.course_id, record_in.pseudo_student_id)
        if not student_id:
            continue
        
        stmt = select(TrajectoryLabel).where(
            TrajectoryLabel.student_id == student_id,
            TrajectoryLabel.course_id == record_in.course_id,
            TrajectoryLabel.week_index == record_in.week_index
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        
        data = record_in.model_dump(exclude={'pseudo_student_id'})
        data['student_id'] = student_id
        
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            db.add(existing)
        else:
            db.add(TrajectoryLabel(**data))
        count += 1
            
    await db.commit()
    return {"status": "ingested", "count": count}


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR))
):
    stmt = select(RiskScore).order_by(RiskScore.created_at.desc()).limit(100)
    res = await db.execute(stmt)
    recent_risks = res.scalars().all()
    
    if not recent_risks:
        return {"active_alerts": 0, "recent_risk_scores": []}
        
    high_risk_count = sum(1 for r in recent_risks if r.risk_tier == "High")
    
    return {
        "active_alerts": high_risk_count,
        "recent_risk_scores": [{"student_id": r.student_id, "score": r.risk_score, "tier": r.risk_tier} for r in recent_risks[:10]]
    }


@router.get("/courses/{course_id}/cohort", response_model=Dict[str, Any])
async def get_cohort_overview(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR))
):
    stmt = select(RiskScore).where(RiskScore.course_id == course_id)
    result = await db.execute(stmt)
    scores = result.scalars().all()
    
    if not scores:
        return {
            "tier_distribution": {"High": 0, "Medium": 0, "Low": 0},
            "top_at_risk": [],
            "avg_risk_trend": []
        }
        
    # Latest week for each student
    latest_week = max(s.week_index for s in scores)
    latest_scores = [s for s in scores if s.week_index == latest_week]
    
    tiers = {"High": 0, "Medium": 0, "Low": 0}
    for s in latest_scores:
        if s.risk_tier in tiers:
            tiers[s.risk_tier] += 1
            
    top_at_risk = sorted(latest_scores, key=lambda x: x.risk_score, reverse=True)[:5]
    
    # Avg trend
    trends = {}
    for s in scores:
        if s.week_index not in trends:
            trends[s.week_index] = []
        trends[s.week_index].append(s.risk_score)
        
    avg_trend = [{"week": w, "avg_risk": sum(v)/len(v)} for w, v in trends.items()]
    avg_trend.sort(key=lambda x: x["week"])
    
    return {
        "tier_distribution": tiers,
        "top_at_risk": [RiskScoreResponse.model_validate(r) for r in top_at_risk],
        "avg_risk_trend": avg_trend
    }


@router.get("/courses/{course_id}/students/{student_id}/risk-detail", response_model=Dict[str, Any])
async def get_risk_detail(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR))
):
    stmt = select(RiskScore).where(RiskScore.course_id == course_id, RiskScore.student_id == student_id).order_by(RiskScore.week_index)
    result = await db.execute(stmt)
    history = result.scalars().all()
    
    if not history:
        return {
            "history": [],
            "latest": None
        }
        
    latest = history[-1]
    
    # We will expand gradebook/attendance summary later when wired.
    return {
        "history": [RiskScoreResponse.model_validate(h) for h in history],
        "latest": {
            "modality_weights": latest.modality_weights,
            "top_features": latest.top_features,
            "c1_snapshot": latest.c1_snapshot,
            "c2_snapshot": latest.c2_snapshot
        },
        "gradebook_summary": {},
        "attendance_summary": {}
    }


@router.get("/courses/{course_id}/risk", response_model=List[RiskScoreResponse])
async def get_course_risk(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR))
):
    stmt = select(RiskScore).where(RiskScore.course_id == course_id).order_by(RiskScore.week_index.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/courses/{course_id}/students/{student_id}/trajectory", response_model=List[TrajectoryLabelResponse])
async def get_student_trajectory(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR))
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
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    from app.services.synthetic import generate_synthetic_data
    await generate_synthetic_data(db, str(course_id))
    await db.commit()
    return {"status": "generated"}


@router.get("/courses/{course_id}/export")
async def export_data(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    from fastapi.responses import StreamingResponse
    from app.services.export import export_training_data
    
    csv_data = await export_training_data(db, str(course_id))
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=training_data_{course_id}.csv"}
    )
