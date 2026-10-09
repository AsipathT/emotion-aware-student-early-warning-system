import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.analytics import WeeklyFeature
from app.models.assessment import Assignment, AssignmentSubmission
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.behaviour import ClickEvent, UserSession
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole


@pytest_asyncio.fixture
async def aggregation_setup(db_session: AsyncSession):
    """Seed a course starting 20 days ago with data across weeks 0, 1, and 2."""
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id,
        email="admin@lms.edu",
        hashed_password=hash_password("Admin123"),
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    stu_id = uuid.uuid4()
    stu = User(
        id=stu_id,
        email="student@lms.edu",
        hashed_password=hash_password("Student123"),
        full_name="Stu",
        role=UserRole.STUDENT,
        is_active=True,
    )

    lec_id = uuid.uuid4()
    lec = User(
        id=lec_id,
        email="lecturer@lms.edu",
        hashed_password=hash_password("Lecturer123"),
        full_name="Lec",
        role=UserRole.LECTURER,
        is_active=True,
    )

    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=20)
    course = Course(
        id=course_id,
        title="Agg Course",
        lecturer_id=lec_id,
        start_date=start,
        end_date=start + timedelta(days=100),
    )

    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, status="active")

    db_session.add_all([admin, stu, lec, course, enrollment])
    await db_session.flush()

    # Base datetime for week 0
    w0_base = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)

    # --- Week 0 (days 0..6): 2 sessions, 3 clicks on 2 different days ---
    s0a = UserSession(
        id=uuid.uuid4(),
        user_id=stu_id,
        login_at=w0_base + timedelta(hours=1),
        logout_at=w0_base + timedelta(hours=2),
        duration_seconds=3600,
    )
    s0b = UserSession(
        id=uuid.uuid4(),
        user_id=stu_id,
        login_at=w0_base + timedelta(days=2, hours=3),
        logout_at=w0_base + timedelta(days=2, hours=4),
        duration_seconds=3600,
    )
    db_session.add_all([s0a, s0b])
    await db_session.flush()

    e0a = ClickEvent(
        id=uuid.uuid4(),
        user_id=stu_id,
        course_id=course_id,
        session_id=s0a.id,
        event_type="PAGE_VIEW",
        resource_type="module",
        resource_id=str(uuid.uuid4()),
        occurred_at=w0_base + timedelta(hours=1, minutes=10),
    )
    e0b = ClickEvent(
        id=uuid.uuid4(),
        user_id=stu_id,
        course_id=course_id,
        session_id=s0a.id,
        event_type="VIDEO_PLAY",
        resource_type="video",
        resource_id=str(uuid.uuid4()),
        occurred_at=w0_base + timedelta(hours=1, minutes=20),
    )
    e0c = ClickEvent(
        id=uuid.uuid4(),
        user_id=stu_id,
        course_id=course_id,
        session_id=s0b.id,
        event_type="PAGE_VIEW",
        resource_type="module",
        resource_id=str(uuid.uuid4()),
        occurred_at=w0_base + timedelta(days=2, hours=3, minutes=10),
    )
    db_session.add_all([e0a, e0b, e0c])

    # Week 0 Attendance: 1 session on day 1 -> Student present
    att_s0 = AttendanceSession(
        id=uuid.uuid4(),
        course_id=course_id,
        title="L0",
        session_date=start + timedelta(days=1),
        created_by=lec_id,
    )
    db_session.add(att_s0)
    await db_session.flush()
    att_r0 = AttendanceRecord(
        id=uuid.uuid4(),
        session_id=att_s0.id,
        student_id=stu_id,
        status="present",
        marked_by=lec_id,
    )
    db_session.add(att_r0)

    # Week 0 Assessment: Assignment A1 due on day 5, submitted on day 4 (on time)
    ass1 = Assignment(
        id=uuid.uuid4(),
        course_id=course_id,
        title="HW-A1",
        max_score=100.0,
        weight=1.0,
        is_published=True,
        due_at=w0_base + timedelta(days=5),
    )
    db_session.add(ass1)
    await db_session.flush()

    sub1 = AssignmentSubmission(
        id=uuid.uuid4(),
        assignment_id=ass1.id,
        student_id=stu_id,
        content_text="answer1",
        submitted_at=w0_base + timedelta(days=4),
        is_late=False,
        delay_days=0,
        score=85.0,
        graded_by=lec_id,
        graded_at=w0_base + timedelta(days=4, hours=2),
    )
    db_session.add(sub1)
    await db_session.flush()

    gb1 = GradebookEntry(
        id=uuid.uuid4(),
        course_id=course_id,
        student_id=stu_id,
        item_type="assignment",
        item_id=ass1.id,
        title="HW-A1",
        score=85.0,
        max_score=100.0,
        weight=1.0,
        recorded_at=w0_base + timedelta(days=4, hours=2),
    )
    db_session.add(gb1)

    # --- Week 1 (days 7..13): 1 session, 1 click on day 8 ---
    w1_base = w0_base + timedelta(days=7)
    s1 = UserSession(
        id=uuid.uuid4(),
        user_id=stu_id,
        login_at=w1_base + timedelta(days=1, hours=5),
        logout_at=w1_base + timedelta(days=1, hours=6),
        duration_seconds=3600,
    )
    db_session.add(s1)
    await db_session.flush()

    e1 = ClickEvent(
        id=uuid.uuid4(),
        user_id=stu_id,
        course_id=course_id,
        session_id=s1.id,
        event_type="FORUM_POST",
        resource_type="forum",
        resource_id=str(uuid.uuid4()),
        occurred_at=w1_base + timedelta(days=1, hours=5, minutes=15),
    )
    db_session.add(e1)

    # Week 1 Attendance: 1 session on day 8 -> Student absent
    att_s1 = AttendanceSession(
        id=uuid.uuid4(),
        course_id=course_id,
        title="L1",
        session_date=start + timedelta(days=8),
        created_by=lec_id,
    )
    db_session.add(att_s1)
    await db_session.flush()
    att_r1 = AttendanceRecord(
        id=uuid.uuid4(),
        session_id=att_s1.id,
        student_id=stu_id,
        status="absent",
        marked_by=lec_id,
    )
    db_session.add(att_r1)

    # Week 1 Assessment: Assignment A2 due on day 10, NOT submitted by student
    ass2 = Assignment(
        id=uuid.uuid4(),
        course_id=course_id,
        title="HW-A2",
        max_score=100.0,
        weight=1.0,
        is_published=True,
        due_at=w0_base + timedelta(days=10),
    )
    db_session.add(ass2)

    # Week 1 Gradebook: Quiz Q1 recorded on day 9 (score=40, max=100, weight=1.0)
    quiz_id = uuid.uuid4()
    gb2 = GradebookEntry(
        id=uuid.uuid4(),
        course_id=course_id,
        student_id=stu_id,
        item_type="quiz",
        item_id=quiz_id,
        title="Quiz 1",
        score=40.0,
        max_score=100.0,
        weight=1.0,
        recorded_at=w0_base + timedelta(days=9),
    )
    db_session.add(gb2)

    # --- Week 2 (days 14..20): EMPTY week (0 sessions, 0 clicks, 0 new assessments) ---

    await db_session.commit()

    return {
        "admin_id": admin_id,
        "stu_id": stu_id,
        "lec_id": lec_id,
        "course_id": course_id,
        "start": start,
    }


@pytest.mark.asyncio
async def test_week_isolation(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """Each week's clicks/sessions/active_days include ONLY that week's events (weeks 0, 1, 2)."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"],
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()
    assert len(rows) == 3, f"Expected 3 weeks (0, 1, 2), got {len(rows)}"

    w0, w1, w2 = rows[0], rows[1], rows[2]

    # Week 0: 2 sessions, 3 clicks, 2 active days (days 0 and 2)
    assert w0.week_index == 0
    assert w0.session_frequency == 2, f"W0 sessions: {w0.session_frequency}"
    assert w0.clicks_total == 3, f"W0 clicks: {w0.clicks_total}"
    assert w0.active_days == 2, f"W0 active_days: {w0.active_days}"

    # Week 1: 1 session, 1 click, 1 active day (day 8). Proves Week 0 events NOT counted in Week 1!
    assert w1.week_index == 1
    assert w1.session_frequency == 1, f"W1 sessions: {w1.session_frequency}"
    assert w1.clicks_total == 1, f"W1 clicks: {w1.clicks_total}"
    assert w1.active_days == 1, f"W1 active_days: {w1.active_days}"

    # Week 2: empty week -> 0 sessions, 0 clicks, 0 active days. Proves Week 0/1 NOT counted in Week 2!
    assert w2.week_index == 2
    assert w2.session_frequency == 0, f"W2 sessions: {w2.session_frequency}"
    assert w2.clicks_total == 0, f"W2 clicks: {w2.clicks_total}"
    assert w2.active_days == 0, f"W2 active_days: {w2.active_days}"


@pytest.mark.asyncio
async def test_active_days_calculation(client: AsyncClient, db_session: AsyncSession):
    """Assert active_days: 5 clicks on same day = 1 active day; 1 click on each of 3 different days = 3 active days."""
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id, email="admin2@lms.edu", hashed_password=hash_password("Admin123"),
        full_name="Admin2", role=UserRole.ADMIN, is_active=True,
    )
    stu_a = User(
        id=uuid.uuid4(), email="stua@lms.edu", hashed_password=hash_password("Student123"),
        full_name="StuA", role=UserRole.STUDENT, is_active=True,
    )
    stu_b = User(
        id=uuid.uuid4(), email="stub@lms.edu", hashed_password=hash_password("Student123"),
        full_name="StuB", role=UserRole.STUDENT, is_active=True,
    )

    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=6)  # Week 0 only
    course = Course(id=course_id, title="Active Days Course", lecturer_id=admin_id, start_date=start)

    en_a = Enrollment(id=uuid.uuid4(), user_id=stu_a.id, course_id=course_id, status="active")
    en_b = Enrollment(id=uuid.uuid4(), user_id=stu_b.id, course_id=course_id, status="active")

    db_session.add_all([admin, stu_a, stu_b, course, en_a, en_b])
    await db_session.flush()

    w0_base = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)

    # Student A: 5 clicks on the SAME day (day 1)
    for i in range(5):
        db_session.add(
            ClickEvent(
                id=uuid.uuid4(),
                user_id=stu_a.id,
                course_id=course_id,
                event_type="PAGE_VIEW",
                resource_type="module",
                resource_id=str(uuid.uuid4()),
                occurred_at=w0_base + timedelta(days=1, hours=1, minutes=i * 10),
            )
        )

    # Student B: 1 click on each of 3 DIFFERENT days (day 1, day 2, day 3)
    for day in [1, 2, 3]:
        db_session.add(
            ClickEvent(
                id=uuid.uuid4(),
                user_id=stu_b.id,
                course_id=course_id,
                event_type="PAGE_VIEW",
                resource_type="module",
                resource_id=str(uuid.uuid4()),
                occurred_at=w0_base + timedelta(days=day, hours=2),
            )
        )

    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin2@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]

    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # Student A: 5 clicks on same day -> active_days == 1
    res_a = await db_session.execute(
        select(WeeklyFeature).where(WeeklyFeature.student_id == stu_a.id, WeeklyFeature.course_id == course_id)
    )
    wf_a = res_a.scalar_one()
    assert wf_a.clicks_total == 5, f"StuA clicks: {wf_a.clicks_total}"
    assert wf_a.active_days == 1, f"StuA 5 clicks on same day expected 1 active day, got {wf_a.active_days}"

    # Student B: 3 clicks on 3 different days -> active_days == 3
    res_b = await db_session.execute(
        select(WeeklyFeature).where(WeeklyFeature.student_id == stu_b.id, WeeklyFeature.course_id == course_id)
    )
    wf_b = res_b.scalar_one()
    assert wf_b.clicks_total == 3, f"StuB clicks: {wf_b.clicks_total}"
    assert wf_b.active_days == 3, f"StuB 3 clicks on 3 different days expected 3 active days, got {wf_b.active_days}"


@pytest.mark.asyncio
async def test_attendance_rate(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """attendance_rate is present+late / total sessions computed cumulatively up to that week."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"],
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()

    # Week 0: 1 session up to week 0, student present -> rate = 1/1 = 1.0
    assert rows[0].attendance_rate == 1.0, f"W0 att_rate: {rows[0].attendance_rate}"

    # Week 1: 2 sessions total (up to week 1), present in 1, absent in 1 -> 1/2 = 0.5
    assert rows[1].attendance_rate == 0.5, f"W1 att_rate: {rows[1].attendance_rate}"

    # Week 2: still 2 sessions total, same cumulative rate = 0.5
    assert rows[2].attendance_rate == 0.5, f"W2 att_rate: {rows[2].attendance_rate}"


@pytest.mark.asyncio
async def test_missed_assessments_and_score(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """missed_assessments counts assessments due in/before that week with no submission; score_so_far is cumulative."""
    ctx = aggregation_setup

    r = await client.post("/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == ctx["stu_id"],
            WeeklyFeature.course_id == ctx["course_id"],
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()

    # Week 0: A1 due on day 5 and submitted -> missed = 0
    assert rows[0].missed_assessments == 0, f"W0 missed: {rows[0].missed_assessments}"
    # Week 0 score_so_far: 85/100 -> 85.0%
    assert rows[0].score_so_far is not None
    assert abs(rows[0].score_so_far - 85.0) < 0.1, f"W0 score: {rows[0].score_so_far}"
    # Week 0 delay: submitted on time -> 0.0
    assert rows[0].submission_delay_days == 0.0, f"W0 delay: {rows[0].submission_delay_days}"

    # Week 1: A2 due on day 10, NOT submitted -> missed = 1 (A2 missed)
    assert rows[1].missed_assessments == 1, f"W1 missed: {rows[1].missed_assessments}"
    # Week 1 score_so_far: A1 (85/100, weight 1) + Q1 (40/100, weight 1) -> (85+40)/(100+100)*100 = 62.5%
    assert rows[1].score_so_far is not None
    assert abs(rows[1].score_so_far - 62.5) < 0.1, f"W1 score: {rows[1].score_so_far}"

    # Week 2: no new assessments -> missed stays 1, score stays 62.5%
    assert rows[2].missed_assessments == 1, f"W2 missed: {rows[2].missed_assessments}"
    assert abs(rows[2].score_so_far - 62.5) < 0.1, f"W2 score: {rows[2].score_so_far}"


@pytest.mark.asyncio
async def test_withdrawn_student(client: AsyncClient, db_session: AsyncSession):
    """Withdrawn student gets no rows for weeks starting at or after withdrawn_at."""
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id, email="admin3@lms.edu", hashed_password=hash_password("Admin123"),
        full_name="Admin3", role=UserRole.ADMIN, is_active=True,
    )
    stu_id = uuid.uuid4()
    stu = User(
        id=stu_id, email="student3@lms.edu", hashed_password=hash_password("Student123"),
        full_name="Stu3", role=UserRole.STUDENT, is_active=True,
    )

    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=20)
    course = Course(
        id=course_id, title="WD Course", lecturer_id=admin_id,
        start_date=start, end_date=start + timedelta(days=100),
    )

    # Student withdrew on day 7 (start of Week 1)
    withdrawn_at = datetime.combine(start + timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    enrollment = Enrollment(
        id=uuid.uuid4(), user_id=stu_id, course_id=course_id,
        status="withdrawn", withdrawn_at=withdrawn_at,
    )

    db_session.add_all([admin, stu, course, enrollment])
    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin3@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]
    r = await client.post("/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == stu_id,
            WeeklyFeature.course_id == course_id,
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()
    # Only Week 0 exists; Weeks 1 and 2 start at or after withdrawn_at
    assert len(rows) == 1, f"Expected 1 row (Week 0) for withdrawn student, got {len(rows)}"
    assert rows[0].week_index == 0


@pytest.mark.asyncio
async def test_null_start_date_returns_400(client: AsyncClient, db_session: AsyncSession):
    """Course with start_date=None returns clear 400 Bad Request when targeted for aggregation."""
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id, email="admin4@lms.edu", hashed_password=hash_password("Admin123"),
        full_name="Admin4", role=UserRole.ADMIN, is_active=True,
    )
    course_id = uuid.uuid4()
    course = Course(id=course_id, title="Null Start Course", lecturer_id=admin_id, start_date=None)

    db_session.add_all([admin, course])
    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin4@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]

    # When targeted specifically, course with null start_date returns 400
    r = await client.post(
        f"/api/v1/jobs/aggregate-weekly?course_id={course_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "start_date" in r.text.lower()


@pytest.mark.asyncio
async def test_course_no_events_returns_zeros_not_500(client: AsyncClient, db_session: AsyncSession):
    """Course with start_date and enrolled student but NO events returns 0s, not 500."""
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id, email="admin5@lms.edu", hashed_password=hash_password("Admin123"),
        full_name="Admin5", role=UserRole.ADMIN, is_active=True,
    )
    stu_id = uuid.uuid4()
    stu = User(
        id=stu_id, email="student5@lms.edu", hashed_password=hash_password("Student123"),
        full_name="Stu5", role=UserRole.STUDENT, is_active=True,
    )
    course_id = uuid.uuid4()
    start = date.today() - timedelta(days=20)
    course = Course(id=course_id, title="Zero Events Course", lecturer_id=admin_id, start_date=start)
    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, status="active")

    db_session.add_all([admin, stu, course, enrollment])
    await db_session.commit()

    r = await client.post("/api/v1/auth/login", json={"email": "admin5@lms.edu", "password": "Admin123"})
    token = r.json()["access_token"]

    r = await client.post(
        f"/api/v1/jobs/aggregate-weekly?course_id={course_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    res = await db_session.execute(
        select(WeeklyFeature).where(
            WeeklyFeature.student_id == stu_id,
            WeeklyFeature.course_id == course_id,
        ).order_by(WeeklyFeature.week_index)
    )
    rows = res.scalars().all()
    assert len(rows) == 3, f"Expected 3 weeks, got {len(rows)}"

    for row in rows:
        assert row.session_frequency == 0
        assert row.clicks_total == 0
        assert row.active_days == 0
        assert row.missed_assessments == 0
        assert row.attendance_rate is None
        assert row.score_so_far is None
        assert row.submission_delay_days is None


@pytest.mark.asyncio
async def test_idempotency(client: AsyncClient, db_session: AsyncSession, aggregation_setup):
    """Running aggregation twice produces the same number of rows (idempotent, does not duplicate)."""
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

    assert count1 == count2, f"Idempotency failed: count before={count1}, count after={count2}"
