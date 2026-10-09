import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.analytics import WeeklyFeature
from app.models.behaviour import ClickEvent, UserSession
from app.models.assessment import Assignment, AssignmentSubmission, Quiz, QuizAttempt
from app.models.attendance import AttendanceSession, AttendanceRecord
from app.models.gradebook import GradebookEntry

logger = logging.getLogger(__name__)


async def compute_weekly_features(db: AsyncSession) -> int:
    """
    Computes weekly features for all enrollments in all courses with start_date.
    Each week's stats are isolated to [week_start, week_end).
    Withdrawn students get no rows for weeks after withdrawn_at.
    Courses with start_date=NULL are skipped with a logged warning.
    Returns the number of records upserted.
    """
    now = datetime.now(timezone.utc)
    now_date = now.date()

    # Log courses with NULL start_date
    null_stmt = select(Course).where(Course.start_date.is_(None))
    null_result = await db.execute(null_stmt)
    null_courses = null_result.scalars().all()
    for nc in null_courses:
        logger.warning("Skipping course %s (%s): start_date is NULL", nc.id, nc.title)

    stmt = select(Course).where(Course.start_date.isnot(None))
    result = await db.execute(stmt)
    courses = result.scalars().all()

    count = 0

    for course in courses:
        delta_days = (now_date - course.start_date).days
        if delta_days < 0:
            continue

        current_week = (delta_days // 7) + 1

        en_stmt = select(Enrollment).where(Enrollment.course_id == course.id)
        en_result = await db.execute(en_stmt)
        enrollments = en_result.scalars().all()

        for en in enrollments:
            student_id = en.user_id

            for week_idx in range(1, current_week + 1):
                week_start_dt = datetime.combine(
                    course.start_date, datetime.min.time()
                ).replace(tzinfo=timezone.utc)
                week_start = week_start_dt + timedelta(days=(week_idx - 1) * 7)
                week_end = week_start + timedelta(days=7)

                # Check withdrawal: skip weeks starting at or after withdrawn_at
                if en.status == "withdrawn" and en.withdrawn_at:
                    if week_start >= en.withdrawn_at:
                        continue

                # 1. session_frequency: count of login sessions this week
                sess_stmt = select(func.count(UserSession.id)).where(
                    UserSession.user_id == student_id,
                    UserSession.login_at >= week_start,
                    UserSession.login_at < week_end,
                )
                session_frequency = (await db.execute(sess_stmt)).scalar() or 0

                # 2. clicks_total: click events this week for this course
                clk_stmt = select(func.count(ClickEvent.id)).where(
                    ClickEvent.user_id == student_id,
                    ClickEvent.course_id == course.id,
                    ClickEvent.occurred_at >= week_start,
                    ClickEvent.occurred_at < week_end,
                )
                clicks_total = (await db.execute(clk_stmt)).scalar() or 0

                # 3. active_days: distinct dates with at least one session login
                ad_stmt = select(
                    func.count(func.distinct(func.date_trunc('day', UserSession.login_at)))
                ).where(
                    UserSession.user_id == student_id,
                    UserSession.login_at >= week_start,
                    UserSession.login_at < week_end,
                )
                active_days = (await db.execute(ad_stmt)).scalar() or 0

                # 4. attendance_rate: present+late / total sessions up to this week
                att_total_stmt = select(func.count(AttendanceSession.id)).where(
                    AttendanceSession.course_id == course.id,
                    AttendanceSession.session_date >= course.start_date,
                    AttendanceSession.session_date < (course.start_date + timedelta(days=week_idx * 7)),
                )
                att_total = (await db.execute(att_total_stmt)).scalar() or 0

                if att_total > 0:
                    att_present_stmt = select(func.count(AttendanceRecord.id)).where(
                        AttendanceRecord.student_id == student_id,
                        AttendanceRecord.session_id.in_(
                            select(AttendanceSession.id).where(
                                AttendanceSession.course_id == course.id,
                                AttendanceSession.session_date >= course.start_date,
                                AttendanceSession.session_date < (course.start_date + timedelta(days=week_idx * 7)),
                            )
                        ),
                        AttendanceRecord.status.in_(["present", "late"]),
                    )
                    att_present = (await db.execute(att_present_stmt)).scalar() or 0
                    attendance_rate = att_present / att_total
                else:
                    attendance_rate = None

                # 5. missed_assessments: assignments due up to week_end that student didn't submit
                due_assignments_stmt = select(func.count(Assignment.id)).where(
                    Assignment.course_id == course.id,
                    Assignment.is_published == True,
                    Assignment.due_at.isnot(None),
                    Assignment.due_at < week_end,
                )
                due_count = (await db.execute(due_assignments_stmt)).scalar() or 0

                submitted_stmt = select(func.count(AssignmentSubmission.id)).where(
                    AssignmentSubmission.student_id == student_id,
                    AssignmentSubmission.assignment_id.in_(
                        select(Assignment.id).where(
                            Assignment.course_id == course.id,
                            Assignment.is_published == True,
                            Assignment.due_at.isnot(None),
                            Assignment.due_at < week_end,
                        )
                    ),
                )
                submitted_count = (await db.execute(submitted_stmt)).scalar() or 0
                missed_assessments = due_count - submitted_count

                # 6. submission_delay_days: avg delay for submissions graded up to week_end
                delay_stmt = select(
                    func.avg(AssignmentSubmission.delay_days)
                ).where(
                    AssignmentSubmission.student_id == student_id,
                    AssignmentSubmission.assignment_id.in_(
                        select(Assignment.id).where(Assignment.course_id == course.id)
                    ),
                    AssignmentSubmission.submitted_at < week_end,
                )
                submission_delay_days = (await db.execute(delay_stmt)).scalar()

                # 7. score_so_far: weighted average from gradebook entries up to week_end
                gb_stmt = select(
                    func.sum(GradebookEntry.score * GradebookEntry.weight),
                    func.sum(GradebookEntry.max_score * GradebookEntry.weight),
                ).where(
                    GradebookEntry.student_id == student_id,
                    GradebookEntry.course_id == course.id,
                    GradebookEntry.recorded_at < week_end,
                )
                gb_res = await db.execute(gb_stmt)
                gb_row = gb_res.one_or_none()
                if gb_row and gb_row[0] is not None and gb_row[1] and gb_row[1] > 0:
                    score_so_far = (gb_row[0] / gb_row[1]) * 100.0
                else:
                    score_so_far = None

                # Upsert WeeklyFeature
                wf_stmt = select(WeeklyFeature).where(
                    WeeklyFeature.student_id == student_id,
                    WeeklyFeature.course_id == course.id,
                    WeeklyFeature.week_index == week_idx,
                )
                wf = (await db.execute(wf_stmt)).scalar_one_or_none()

                if not wf:
                    wf = WeeklyFeature(
                        student_id=student_id,
                        course_id=course.id,
                        week_index=week_idx,
                        week_start=course.start_date + timedelta(days=(week_idx - 1) * 7),
                        session_frequency=session_frequency,
                        clicks_total=clicks_total,
                        active_days=active_days,
                        attendance_rate=attendance_rate,
                        missed_assessments=missed_assessments,
                        submission_delay_days=submission_delay_days,
                        score_so_far=score_so_far,
                        prev_attempts=0,
                    )
                    db.add(wf)
                else:
                    wf.session_frequency = session_frequency
                    wf.clicks_total = clicks_total
                    wf.active_days = active_days
                    wf.attendance_rate = attendance_rate
                    wf.missed_assessments = missed_assessments
                    wf.submission_delay_days = submission_delay_days
                    wf.score_so_far = score_so_far
                    wf.computed_at = now

                count += 1

    await db.flush()
    return count
