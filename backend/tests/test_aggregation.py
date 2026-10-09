import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.behaviour import ClickEvent, UserSession
from app.models.assessment import Assignment, AssignmentSubmission
from app.models.attendance import AttendanceSession, AttendanceRecord
from app.models.gradebook import GradebookEntry
from app.models.analytics import WeeklyFeature
from app.core.security import hash_password
from datetime import datetime, timedelta, timezone, date
import uuid


@pytest_asyncio.fixture
async def aggregation_setup(db_session: AsyncSession):
    """Seed a course starting 21 days ago with 3 weeks of diverse data."""
    admin_id = uuid.uuid4()
    admin = User(id=admin_id, email="admin@lms.edu", hashed_password=hash_password("Admin123"),
                 full_name="Admin", role=UserRole.ADMIN, is_active=True)

    stu_id = uuid.uuid4()
    stu = User(id=stu_id, email="student@lms.edu", hashed_password=hash_password("Student123"),
               full_name="Stu", role=UserRole.STUDENT, is_active=True)

    lec_id = uuid.uuid4()
    lec = User(id=lec_id, email="lecturer@lms.edu", hashed_password=hash_password("Lecturer123"),
               full_name="Lec", role=UserRole.LECTURER, is_active=True)

    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=21)
    course = Course(id=course_id, title="Agg Course", lecturer_id=lec_id,
                    start_date=start, end_date=start + timedelta(days=100))

    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, status="active")

    db_session.add_all([admin, stu, lec, course, enrollment])
    await db_session.flush()

    # --- Week 1 events (start + 0..6 days) ---
    w1_base = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
    # 2 sessions on 2 different days
    s1a = UserSession(id=uuid.uuid4(), user_id=stu_id, login_at=w1_base + timedelta(hours=1),
                      logout_at=w1_base + timedelta(hours=2), duration_seconds=3600)
    s1b = UserSession(id=uuid.uuid4(), user_id=stu_id, login_at=w1_base + timedelta(days=2, hours=3),
                      logout_at=w1_base + timedelta(days=2, hours=4), duration_seconds=3600)
    # 3 click events in week 1
    e1a = ClickEvent(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, session_id=s1a.id,
                     event_type="PAGE_VIEW", resource_type="module", resource_id=str(uuid.uuid4()),
                     occurred_at=w1_base + timedelta(hours=1, minutes=10))
    e1b = ClickEvent(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, session_id=s1a.id,
                     event_type="VIDEO_PLAY", resource_type="video", resource_id=str(uuid.uuid4()),
                     occurred_at=w1_base + timedelta(hours=1, minutes=20))
    e1c = ClickEvent(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, session_id=s1b.id,
                     event_type="PAGE_VIEW", resource_type="module", resource_id=str(uuid.uuid4()),
                     occurred_at=w1_base + timedelta(days=2, hours=3, minutes=10))

    db_session.add_all([s1a, s1b])
    await db_session.flush()
    db_session.add_all([e1a, e1b, e1c])

    # --- Week 2 events (start + 7..13 days) ---
    w2_base = w1_base + timedelta(days=7)
    s2 = UserSession(id=uuid.uuid4(), user_id=stu_id, login_at=w2_base + timedelta(hours=5),
                     logout_at=w2_base + timedelta(hours=6), duration_seconds=3600)
    e2 = ClickEvent(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, session_id=s2.id,
                    event_type="FORUM_POST", resource_type="forum", resource_id=str(uuid.uuid4()),
                    occurred_at=w2_base + timedelta(hours=5, minutes=15))

    db_session.add(s2)
    await db_session.flush()
    db_session.add(e2)

    # --- Week 3 events (start + 14..20 days): NO events ---
    # (empty week)

    # Attendance: 1 session in week 1, 1 session in week 2
    att_s1 = AttendanceSession(id=uuid.uuid4(), course_id=course_id, title="L1",
                               session_date=start + timedelta(days=1), created_by=lec_id)
    att_s2 = AttendanceSession(id=uuid.uuid4(), course_id=course_id, title="L2",
                               session_date=start + timedelta(days=8), created_by=lec_id)

    db_session.add_all([att_s1, att_s2])
    await db_session.flush()

    # Student present in week 1, absent in week 2
    att_r1 = AttendanceRecord(id=uuid.uuid4(), session_id=att_s1.id, student_id=stu_id,
                              status="present", marked_by=lec_id)
    att_r2 = AttendanceRecord(id=uuid.uuid4(), session_id=att_s2.id, student_id=stu_id,
                              status="absent", marked_by=lec_id)
    db_session.add_all([att_r1, att_r2])

    # Assignment due in week 1, submitted on time with score
    ass = Assignment(id=uuid.uuid4(), course_id=course_id, title="HW-A1",
                     max_score=100.0, weight=1.0, is_published=True,
                     due_at=w1_base + timedelta(days=5))
    db_session.add(ass)
    await db_session.flush()

    sub = AssignmentSubmission(id=uuid.uuid4(), assignment_id=ass.id, student_id=stu_id,
                               content_text="ans", is_late=False, delay_days=0, score=85.0,
                               graded_by=lec_id, graded_at=w1_base + timedelta(days=6))
    db_session.add(sub)
    await db_session.flush()

    # Gradebook entry for the assignment
    gb = GradebookEntry(id=uuid.uuid4(), course_id=course_id, student_id=stu_id,
                        item_type="assignment", item_id=ass.id, title="HW-A1",
                        score=85.0, max_score=100.0, weight=1.0,
                        recorded_at=w1_base + timedelta(days=6))
    db_session.add(gb)

    await db_session.commit()

    return {
        "admin_id": admin_id, "stu_id": stu_id, "lec_id": lec_id,
        "course_id": course_id, "start": start,
    }


@pytest.mark.asyncio
async def test_week_isolation(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """Each week's clicks/sessions/active_days include ONLY that week's events."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]

    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"]
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()
    assert len(rows) == 3, f"Expected 3 weeks, got {len(rows)}"

    w1, w2, w3 = rows[0], rows[1], rows[2]

    # Week 1: 2 sessions, 3 clicks, 2 active days
    assert w1.week_index == 1
    assert w1.session_frequency == 2, f"W1 sessions: {w1.session_frequency}"
    assert w1.clicks_total == 3, f"W1 clicks: {w1.clicks_total}"
    assert w1.active_days == 2, f"W1 active_days: {w1.active_days}"

    # Week 2: 1 session, 1 click, 1 active day
    assert w2.week_index == 2
    assert w2.session_frequency == 1, f"W2 sessions: {w2.session_frequency}"
    assert w2.clicks_total == 1, f"W2 clicks: {w2.clicks_total}"
    assert w2.active_days == 1, f"W2 active_days: {w2.active_days}"

    # Week 3: empty week -> 0 sessions, 0 clicks, 0 active days (row still exists)
    assert w3.week_index == 3
    assert w3.session_frequency == 0, f"W3 sessions: {w3.session_frequency}"
    assert w3.clicks_total == 0, f"W3 clicks: {w3.clicks_total}"
    assert w3.active_days == 0, f"W3 active_days: {w3.active_days}"


@pytest.mark.asyncio
async def test_attendance_rate(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """attendance_rate is present+late / total sessions up to that week."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"]
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()

    # Week 1: 1 session, student present -> rate = 1/1 = 1.0
    assert rows[0].attendance_rate == 1.0, f"W1 att_rate: {rows[0].attendance_rate}"

    # Week 2: 2 sessions total (up to week 2), student present in 1, absent in 1 -> 1/2 = 0.5
    assert rows[1].attendance_rate == 0.5, f"W2 att_rate: {rows[1].attendance_rate}"

    # Week 3: still 2 sessions total, same rate
    assert rows[2].attendance_rate == 0.5, f"W3 att_rate: {rows[2].attendance_rate}"


@pytest.mark.asyncio
async def test_missed_assessments_and_score(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """missed_assessments and score_so_far computed from data up to that week."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"]
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()

    # Assignment due in week 1, submitted -> missed=0 for week 1+
    assert rows[0].missed_assessments == 0, f"W1 missed: {rows[0].missed_assessments}"
    assert rows[1].missed_assessments == 0, f"W2 missed: {rows[1].missed_assessments}"

    # score_so_far: assignment graded in week 1 with 85/100 -> 85.0% in all weeks
    assert rows[0].score_so_far is not None
    assert abs(rows[0].score_so_far - 85.0) < 0.1, f"W1 score: {rows[0].score_so_far}"

    # submission_delay_days: 0 since submitted on time
    assert rows[0].submission_delay_days == 0.0, f"W1 delay: {rows[0].submission_delay_days}"


@pytest.mark.asyncio
async def test_withdrawn_student(client: AsyncClient, db_session: AsyncSession):
    """Withdrawn student gets no rows for weeks after withdrawn_at."""
    admin_id = uuid.uuid4()
    admin = User(id=admin_id, email="admin@lms.edu", hashed_password=hash_password("Admin123"),
                 full_name="Admin", role=UserRole.ADMIN, is_active=True)
    stu_id = uuid.uuid4()
    stu = User(id=stu_id, email="student@lms.edu", hashed_password=hash_password("Student123"),
               full_name="Stu", role=UserRole.STUDENT, is_active=True)

    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=21)
    course = Course(id=course_id, title="WD Course", lecturer_id=admin_id,
                    start_date=start, end_date=start + timedelta(days=100))

    # Withdrawn at start of week 2
    withdrawn_at = datetime.combine(start + timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id,
                            status="withdrawn", withdrawn_at=withdrawn_at)

    db_session.add_all([admin, stu, course, enrollment])
    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == stu_id,
            WeeklyFeature.course_id == course_id
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()
    # Only week 1 should exist; weeks 2 and 3 start at or after withdrawn_at
    assert len(rows) == 1, f"Expected 1 row for withdrawn student, got {len(rows)}"
    assert rows[0].week_index == 1


@pytest.mark.asyncio
async def test_null_start_date_skipped(client: AsyncClient, db_session: AsyncSession):
    """Course with start_date=NULL is skipped (no rows created, warning logged)."""
    admin_id = uuid.uuid4()
    admin = User(id=admin_id, email="admin@lms.edu", hashed_password=hash_password("Admin123"),
                 full_name="Admin", role=UserRole.ADMIN, is_active=True)
    stu_id = uuid.uuid4()
    stu = User(id=stu_id, email="student@lms.edu", hashed_password=hash_password("Student123"),
               full_name="Stu", role=UserRole.STUDENT, is_active=True)

    course_id = uuid.uuid4()
    course = Course(id=course_id, title="Null Start Course", lecturer_id=admin_id,
                    start_date=None)

    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, status="active")

    db_session.add_all([admin, stu, course, enrollment])
    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == stu_id,
            WeeklyFeature.course_id == course_id
        )
    )
    rows = res.scalars().all()
    assert len(rows) == 0, f"Expected 0 rows for NULL start_date course, got {len(rows)}"


@pytest.mark.asyncio
async def test_idempotency(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """Running aggregation twice produces the same number of rows."""
    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]

    r1 = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200

    res1 = await db_session.execute(select(func.count(WeeklyFeature.id)))
    count1 = res1.scalar()

    r2 = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200

    res2 = await db_session.execute(select(func.count(WeeklyFeature.id)))
    count2 = res2.scalar()

    assert count1 == count2, f"Idempotency failed: {count1} != {count2}"
