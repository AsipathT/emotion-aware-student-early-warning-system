import csv
import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import WeeklyFeature, AffectWeekly, TrajectoryLabel


async def export_training_data(db: AsyncSession, course_id: str) -> str:
    """
    Produces the flattened training_data.csv joining weekly_features, affect_weekly, 
    and trajectory_labels. (Academic performance is included in weekly_features).
    Note: risk_scores are output predictions, so they are not included in training data.
    """
    # Fetch all data for the course
    wf_stmt = select(WeeklyFeature).where(WeeklyFeature.course_id == course_id)
    wf_res = await db.execute(wf_stmt)
    wfs = wf_res.scalars().all()
    
    affect_stmt = select(AffectWeekly).where(AffectWeekly.course_id == course_id)
    affect_res = await db.execute(affect_stmt)
    affects = {f"{a.student_id}_{a.week_index}": a for a in affect_res.scalars().all()}
    
    traj_stmt = select(TrajectoryLabel).where(TrajectoryLabel.course_id == course_id)
    traj_res = await db.execute(traj_stmt)
    trajs = {f"{t.student_id}_{t.week_index}": t for t in traj_res.scalars().all()}
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "student_id", "course_id", "week_index",
        "session_frequency", "clicks_total", "active_days", "active_duration_trend",
        "submission_delay_days", "video_interaction_intensity", "missed_assessments",
        "prev_attempts", "studied_credits", "attendance_rate", "score_so_far",
        "exam_anxiety", "conceptual_confusion", "academic_helplessness",
        "course_frustration", "motivation_erosion", "confidence", "message_count",
        "trajectory_label"
    ])
    
    for wf in wfs:
        key = f"{wf.student_id}_{wf.week_index}"
        affect = affects.get(key)
        traj = trajs.get(key)
        
        writer.writerow([
            str(wf.student_id), str(wf.course_id), wf.week_index,
            wf.session_frequency, wf.clicks_total, wf.active_days, wf.active_duration_trend,
            wf.submission_delay_days, wf.video_interaction_intensity, wf.missed_assessments,
            wf.prev_attempts, wf.studied_credits, wf.attendance_rate, wf.score_so_far,
            affect.exam_anxiety if affect else None,
            affect.conceptual_confusion if affect else None,
            affect.academic_helplessness if affect else None,
            affect.course_frustration if affect else None,
            affect.motivation_erosion if affect else None,
            affect.confidence if affect else None,
            affect.message_count if affect else 0,
            traj.label if traj else None
        ])
        
    return output.getvalue()
