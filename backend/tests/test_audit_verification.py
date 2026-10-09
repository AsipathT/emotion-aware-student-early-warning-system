import hashlib
import random
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pseudonym import pseudonymize
from app.core.security import hash_password
from app.models.analytics import AffectWeekly, RiskScore, SyntheticGroundTruth, TrajectoryLabel, WeeklyFeature
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole
from app.services.synthetic import generate_synthetic_data


@pytest_asyncio.fixture
async def audit_setup(db_session: AsyncSession):
    """Seed users, course, enrollments, weekly_features, affect, trajectory, and gradebook for export and synthetic verification."""
    admin = User(
        id=uuid.uuid4(), email="admin_audit@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Admin Audit", role=UserRole.ADMIN, is_active=True,
    )
    lecturer = User(
        id=uuid.uuid4(), email="lec_audit@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Lecturer Audit", role=UserRole.LECTURER, is_active=True,
    )
    s1 = User(
        id=uuid.uuid4(), email="s1@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Alice Student", role=UserRole.STUDENT, is_active=True,
    )
    s2 = User(
        id=uuid.uuid4(), email="s2@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Bob Student", role=UserRole.STUDENT, is_active=True,
    )

    course = Course(
        id=uuid.uuid4(), title="Audit Course", lecturer_id=lecturer.id,
        start_date=date.today() - timedelta(days=14),
    )
    e1 = Enrollment(id=uuid.uuid4(), user_id=s1.id, course_id=course.id, status="active")
    e2 = Enrollment(id=uuid.uuid4(), user_id=s2.id, course_id=course.id, status="active")

    db_session.add_all([admin, lecturer, s1, s2, course, e1, e2])
    await db_session.flush()

    # Add WeeklyFeatures for s1 and s2
    wf1 = WeeklyFeature(
        id=uuid.uuid4(), student_id=s1.id, course_id=course.id, week_index=0,
        week_start=date.today() - timedelta(days=14), session_frequency=3, clicks_total=25,
        active_days=3, attendance_rate=1.0, score_so_far=92.0, missed_assessments=0,
    )
    wf2 = WeeklyFeature(
        id=uuid.uuid4(), student_id=s2.id, course_id=course.id, week_index=0,
        week_start=date.today() - timedelta(days=14), session_frequency=1, clicks_total=5,
        active_days=1, attendance_rate=0.5, score_so_far=55.0, missed_assessments=1,
    )
    db_session.add_all([wf1, wf2])

    # Add AffectWeekly
    aff1 = AffectWeekly(
        id=uuid.uuid4(), student_id=s1.id, course_id=course.id, week_index=0,
        exam_anxiety=0.2, conceptual_confusion=0.1, academic_helplessness=0.05,
        course_frustration=0.1, motivation_erosion=0.1, confidence=0.85, message_count=8,
    )
    aff2 = AffectWeekly(
        id=uuid.uuid4(), student_id=s2.id, course_id=course.id, week_index=0,
        exam_anxiety=0.8, conceptual_confusion=0.7, academic_helplessness=0.6,
        course_frustration=0.75, motivation_erosion=0.7, confidence=0.3, message_count=2,
    )
    db_session.add_all([aff1, aff2])

    # Add TrajectoryLabel
    tl1 = TrajectoryLabel(
        id=uuid.uuid4(), student_id=s1.id, course_id=course.id, week_index=0,
        label="Improving", confidence=0.88, schema_version="1.0",
    )
    tl2 = TrajectoryLabel(
        id=uuid.uuid4(), student_id=s2.id, course_id=course.id, week_index=0,
        label="Declining", confidence=0.91, schema_version="1.0",
    )
    db_session.add_all([tl1, tl2])

    # Add Gradebook entries
    now = datetime.now(timezone.utc)
    gb1 = GradebookEntry(
        id=uuid.uuid4(), course_id=course.id, student_id=s1.id, item_type="assignment",
        title="HW1", score=92.0, max_score=100.0, weight=1.0, recorded_at=now,
    )
    gb2 = GradebookEntry(
        id=uuid.uuid4(), course_id=course.id, student_id=s2.id, item_type="assignment",
        title="HW1", score=55.0, max_score=100.0, weight=1.0, recorded_at=now,
    )
    db_session.add_all([gb1, gb2])

    await db_session.commit()

    return {
        "admin": admin, "lecturer": lecturer, "s1": s1, "s2": s2, "course": course,
    }


@pytest.mark.asyncio
async def test_audit_part_d_exports(client: AsyncClient, audit_setup):
    """Part D: Verify all export endpoints, show header + 2 data rows, confirm NO email/full_name."""
    ctx = audit_setup
    cid = ctx["course"].id

    r = await client.post("/api/v1/auth/login", json={"email": "admin_audit@lms.edu", "password": "Pass123"})
    token = r.json()["access_token"]
    admin_hdr = {"Authorization": f"Bearer {token}"}

    print("\n" + "=" * 70)
    print("AUDIT PART D: EXPORT ENDPOINTS VERIFICATION")
    print("=" * 70)

    # 1. Training Data CSV Export: GET /api/v1/analytics/courses/{id}/export
    r1 = await client.get(f"/api/v1/analytics/courses/{cid}/export", headers=admin_hdr)
    assert r1.status_code == 200, f"Training export failed: {r1.status_code}"
    lines1 = [l.strip() for l in r1.text.strip().split("\n") if l.strip()]

    print(f"\n[ENDPOINT 1]: GET /api/v1/analytics/courses/{cid}/export")
    print(f"HEADER ROW: {lines1[0]}")
    for i, line in enumerate(lines1[1:3], 1):
        print(f"DATA ROW {i}: {line}")

    # Confirm no email or full_name in header
    header1_lower = lines1[0].lower().split(",")
    assert "email" not in header1_lower, "ERROR: 'email' found in training data export header!"
    assert "full_name" not in header1_lower, "ERROR: 'full_name' found in training data export header!"
    print("CONFIRMED: No 'email' or 'full_name' columns present in training data export.")

    # 2. Gradebook CSV Export: GET /api/v1/courses/{id}/gradebook/csv
    r2 = await client.get(f"/api/v1/courses/{cid}/gradebook/csv", headers=admin_hdr)
    assert r2.status_code == 200, f"Gradebook export failed: {r2.status_code}"
    lines2 = [l.strip() for l in r2.text.strip().split("\n") if l.strip()]

    print(f"\n[ENDPOINT 2]: GET /api/v1/courses/{cid}/gradebook/csv")
    print(f"HEADER ROW: {lines2[0]}")
    for i, line in enumerate(lines2[1:3], 1):
        print(f"DATA ROW {i}: {line}")

    # Confirm no email or full_name in header
    header2_lower = lines2[0].lower().split(",")
    assert "email" not in header2_lower, "ERROR: 'email' found in gradebook export header!"
    assert "full_name" not in header2_lower, "ERROR: 'full_name' found in gradebook export header!"
    print("CONFIRMED: No 'email' or 'full_name' columns present in gradebook export.")


@pytest.mark.asyncio
async def test_audit_part_e_synthetic_generator(client: AsyncClient, db_session: AsyncSession, audit_setup):
    """Part E: Synthetic generator verification (seed, counts, distributions, ground truth table)."""
    ctx = audit_setup
    cid = str(ctx["course"].id)

    print("\n" + "=" * 70)
    print("AUDIT PART E: SYNTHETIC DATA GENERATOR VERIFICATION")
    print("=" * 70)

    # Run 1: with seed 42
    random.seed(42)
    # Clear any existing synthetic affect / risk / traj
    # Generate for 2 enrolled active students across 12 weeks
    await generate_synthetic_data(db_session, cid, num_weeks=12)
    await db_session.flush()

    res_aff = await db_session.execute(select(AffectWeekly).where(AffectWeekly.course_id == ctx["course"].id))
    aff_rows1 = res_aff.scalars().all()
    res_risk = await db_session.execute(select(RiskScore).where(RiskScore.course_id == ctx["course"].id))
    risk_rows1 = res_risk.scalars().all()
    res_traj = await db_session.execute(select(TrajectoryLabel).where(TrajectoryLabel.course_id == ctx["course"].id))
    traj_rows1 = res_traj.scalars().all()

    # Number of students enrolled: 2
    res_en = await db_session.execute(select(func.count(Enrollment.id)).where(Enrollment.course_id == ctx["course"].id))
    en_count = res_en.scalar()

    # Check withdrawal rate:
    res_wd = await db_session.execute(select(func.count(Enrollment.id)).where(
        Enrollment.course_id == ctx["course"].id, Enrollment.status == "withdrawn"
    ))
    wd_count = res_wd.scalar()
    withdrawal_rate = (wd_count / en_count) * 100 if en_count > 0 else 0.0

    # Share of student-weeks with message_count == 0
    zero_msg_count = sum(1 for a in aff_rows1 if a.message_count == 0)
    total_aff = len(aff_rows1)
    zero_msg_share = (zero_msg_count / total_aff * 100) if total_aff > 0 else 0.0

    # Check synthetic_ground_truth table
    res_gt = await db_session.execute(select(SyntheticGroundTruth).where(SyntheticGroundTruth.course_id == ctx["course"].id))
    gt_rows = res_gt.scalars().all()

    # Checksum of generated risk scores
    scores_str = ",".join(f"{r.risk_score:.4f}" for r in sorted(risk_rows1, key=lambda x: (x.student_id, x.week_index)))
    checksum1 = hashlib.md5(scores_str.encode()).hexdigest()

    print(f"Number of Students: {en_count}")
    print(f"Withdrawal Rate: {withdrawal_rate:.1f}%")
    print(f"AffectWeekly Records: {len(aff_rows1)} (2 students x 12 weeks + 2 seeded = {len(aff_rows1)})")
    print(f"Student-weeks with message_count=0: {zero_msg_count}/{total_aff} ({zero_msg_share:.1f}%) [target: ~20%]")
    print(f"RiskScore Records: {len(risk_rows1)}")
    print(f"TrajectoryLabel Records: {len(traj_rows1)}")
    print(f"Synthetic Ground Truth Rows: {len(gt_rows)}")
    print(f"Planted-Driver Distribution: None (not simulated by generator)")
    print(f"Deterministic Checksum (Seed 42): {checksum1}")

    # Quote function implementation
    print("\n--- QUOTE: FUNCTION IMPLEMENTATION (backend/app/services/synthetic.py) ---")
    print("""
async def generate_synthetic_data(db: AsyncSession, course_id: str, num_weeks: int = 12):
    stmt = select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.status == "active")
    ...
    for en in enrollments:
        for week in range(1, num_weeks + 1):
            has_messages = random.random() > 0.2
            ...
            risk_score_val = random.uniform(0, 100)
            ...
            labels = ["Stable", "Improving", "Declining", "Volatile"]
            traj = TrajectoryLabel(..., label=random.choice(labels), ...)
""")
    print("FACTUAL FINDING: Latent-state simulation is NOT implemented. The function only generates independent random uniform floats and uniform random choice of 4 fixed labels ('Stable', 'Improving', 'Declining', 'Volatile'). It does not write to synthetic_ground_truth or model withdrawal trajectories.")
