import random
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.analytics import AffectWeekly, RiskScore, TrajectoryLabel


async def generate_synthetic_data(db: AsyncSession, course_id: str, num_weeks: int = 12):
    """
    Generates synthetic affect_weekly, risk_scores, and trajectory_labels for all 
    enrolled students in a given course.
    """
    # Get enrollments
    stmt = select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.status == "active")
    res = await db.execute(stmt)
    enrollments = res.scalars().all()
    
    now = datetime.now(timezone.utc)
    
    for en in enrollments:
        for week in range(1, num_weeks + 1):
            
            # 1. AffectWeekly (20% chance of no messages)
            has_messages = random.random() > 0.2
            
            if has_messages:
                affect = AffectWeekly(
                    student_id=en.user_id,
                    course_id=course_id,
                    week_index=week,
                    exam_anxiety=random.uniform(0.1, 0.9),
                    conceptual_confusion=random.uniform(0.1, 0.9),
                    academic_helplessness=random.uniform(0.1, 0.9),
                    course_frustration=random.uniform(0.1, 0.9),
                    motivation_erosion=random.uniform(0.1, 0.9),
                    confidence=random.uniform(0.1, 0.9),
                    message_count=random.randint(1, 20),
                    created_at=now
                )
            else:
                affect = AffectWeekly(
                    student_id=en.user_id,
                    course_id=course_id,
                    week_index=week,
                    exam_anxiety=None,
                    conceptual_confusion=None,
                    academic_helplessness=None,
                    course_frustration=None,
                    motivation_erosion=None,
                    confidence=None,
                    message_count=0,
                    created_at=now
                )
            db.add(affect)
            
            # 2. RiskScore
            risk_score_val = random.uniform(0, 100)
            risk_tier = "Low"
            if risk_score_val > 75:
                risk_tier = "High"
            elif risk_score_val > 50:
                risk_tier = "Medium"
                
            risk = RiskScore(
                student_id=en.user_id,
                course_id=course_id,
                week_index=week,
                risk_score=risk_score_val,
                risk_tier=risk_tier,
                calibrated=True,
                schema_version="1.0",
                created_at=now
            )
            db.add(risk)
            
            # 3. TrajectoryLabel
            labels = ["Stable", "Improving", "Declining", "Volatile"]
            traj = TrajectoryLabel(
                student_id=en.user_id,
                course_id=course_id,
                week_index=week,
                label=random.choice(labels),
                p_stable=random.random(),
                p_improving=random.random(),
                p_declining=random.random(),
                p_volatile=random.random(),
                confidence=random.uniform(0.5, 0.99),
                schema_version="1.0",
                created_at=now
            )
            db.add(traj)
            
    await db.flush()
