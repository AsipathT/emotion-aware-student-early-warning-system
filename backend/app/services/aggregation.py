import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.analytics import WeeklyFeature
from app.models.behaviour import ClickEvent, UserSession
from app.models.assessment import Assignment, AssignmentSubmission, Quiz, QuizAttempt

logger = logging.getLogger(__name__)


async def compute_weekly_features(db: AsyncSession) -> int:
    """
    Computes weekly features for all active enrollments.
    For demonstration/architecture validation, it computes basic counts.
    Returns the number of WeeklyFeature records created or updated.
    """
    now = datetime.now(timezone.utc)
    now_date = now.date()

    # Get all courses with start_date
    stmt = select(Course).where(Course.start_date.isnot(None))
    result = await db.execute(stmt)
    courses = result.scalars().all()
    
    count = 0

    for course in courses:
        # Calculate week index: (now - start_date).days // 7 + 1
        delta_days = (now_date - course.start_date).days
        if delta_days < 0:
            continue  # Course hasn't started yet
            
        week_index = (delta_days // 7) + 1
        
        # Get enrollments for this course
        en_stmt = select(Enrollment).where(
            Enrollment.course_id == course.id,
            Enrollment.status == "active"
        )
        en_result = await db.execute(en_stmt)
        enrollments = en_result.scalars().all()
        
        for en in enrollments:
            student_id = en.user_id
            
            # Compute basic stats (Mocked/Simplified for Phase 3B architectural proof)
            # 1. session_frequency
            sess_stmt = select(func.count(UserSession.id)).where(UserSession.user_id == student_id)
            sess_res = await db.execute(sess_stmt)
            session_frequency = sess_res.scalar() or 0
            
            # 2. clicks_total
            clk_stmt = select(func.count(ClickEvent.id)).where(
                ClickEvent.user_id == student_id,
                ClickEvent.course_id == course.id
            )
            clk_res = await db.execute(clk_stmt)
            clicks_total = clk_res.scalar() or 0
            
            # Upsert WeeklyFeature
            wf_stmt = select(WeeklyFeature).where(
                WeeklyFeature.student_id == student_id,
                WeeklyFeature.course_id == course.id,
                WeeklyFeature.week_index == week_index
            )
            wf_res = await db.execute(wf_stmt)
            wf = wf_res.scalar_one_or_none()
            
            if not wf:
                wf = WeeklyFeature(
                    student_id=student_id,
                    course_id=course.id,
                    week_index=week_index,
                    week_start=course.start_date, # simplified
                    session_frequency=session_frequency,
                    clicks_total=clicks_total,
                    active_days=1, # placeholder
                    missed_assessments=0, # placeholder
                    prev_attempts=0
                )
                db.add(wf)
            else:
                wf.session_frequency = session_frequency
                wf.clicks_total = clicks_total
                wf.computed_at = now
                db.add(wf)
                
            count += 1
            
    await db.flush()
    return count
