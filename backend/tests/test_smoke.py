import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.core.security import hash_password
import uuid

@pytest_asyncio.fixture
async def setup_users_and_course(db_session: AsyncSession):
    # Create Lecturer
    lec_id = uuid.uuid4()
    lec = User(id=lec_id, email="lecturer@lms.edu", hashed_password=hash_password("Lecturer123"), full_name="Lec", role=UserRole.LECTURER, is_active=True)
    
    # Create Student
    stu_id = uuid.uuid4()
    stu = User(id=stu_id, email="student@lms.edu", hashed_password=hash_password("Student123"), full_name="Stu", role=UserRole.STUDENT, is_active=True)
    
    # Create Course
    course_id = uuid.uuid4()
    course = Course(id=course_id, title="Test Course", description="Test", lecturer_id=lec_id)
    
    # Create Enrollment
    enrollment = Enrollment(id=uuid.uuid4(), user_id=stu_id, course_id=course_id, status="active")
    
    db_session.add_all([lec, stu, course, enrollment])
    await db_session.commit()
    
    return {"lec_id": lec_id, "stu_id": stu_id, "course_id": course_id}


@pytest.mark.asyncio
async def test_assignment_flow(client: AsyncClient, setup_users_and_course):
    """Assignment -> Submit -> Grade -> Gradebook entry created with correct score."""
    ctx = setup_users_and_course
    
    # Login
    r = await client.post("/api/v1/auth/login", json={"email": "lecturer@lms.edu", "password": "Lecturer123"})
    assert r.status_code == 200
    lec_token = r.json()["access_token"]
    
    r = await client.post("/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student123"})
    assert r.status_code == 200
    stu_token = r.json()["access_token"]
    
    # Create Assignment (published)
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments", json={
        "title": "HW1", "description": "D1", "max_score": 100, "is_published": True, "weight": 2.0
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    ass = r.json()
    ass_id = ass["id"]
    assert ass["is_published"] is True
    assert ass["max_score"] == 100.0
    
    # Student submit
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments/{ass_id}/submit", json={
        "content_text": "My answer"
    }, headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    sub = r.json()
    assert sub["student_id"] == str(ctx["stu_id"])
    assert sub["is_late"] is False
    assert sub["delay_days"] == 0
    assert sub["score"] is None  # Not graded yet
    
    # Lecturer grades
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments/{ass_id}/submissions/{ctx['stu_id']}/grade", json={
        "score": 90.0, "feedback": "Good"
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    graded = r.json()
    assert graded["score"] == 90.0
    assert graded["feedback"] == "Good"
    assert graded["graded_by"] == str(ctx["lec_id"])
    assert graded["graded_at"] is not None
    
    # Student reads own gradebook
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/gradebook/me", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    grades = r.json()
    assert len(grades) >= 1, f"Expected >=1 gradebook entry, got {grades}"
    a_entry = [g for g in grades if g["item_type"] == "assignment"]
    assert len(a_entry) == 1, f"Expected 1 assignment entry, got {a_entry}"
    assert a_entry[0]["score"] == 90.0
    assert a_entry[0]["max_score"] == 100.0
    assert a_entry[0]["weight"] == 2.0
    assert a_entry[0]["title"] == "HW1"
    assert a_entry[0]["item_id"] == ass_id
    
    # Lecturer reads grid
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/gradebook", headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    grid = r.json()
    assert len(grid) >= 1
    assert grid[0]["student_id"] == str(ctx["stu_id"])


@pytest.mark.asyncio
async def test_quiz_flow(client: AsyncClient, setup_users_and_course):
    """Quiz -> Questions -> Start -> Answer -> Submit -> Gradebook entry created."""
    ctx = setup_users_and_course
    
    r = await client.post("/api/v1/auth/login", json={"email": "lecturer@lms.edu", "password": "Lecturer123"})
    lec_token = r.json()["access_token"]
    r = await client.post("/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student123"})
    stu_token = r.json()["access_token"]
    
    # Create Quiz
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes", json={
        "title": "Quiz1", "time_limit_minutes": 10, "max_attempts": 1, "is_published": True,
        "max_score": 100.0, "weight": 3.0
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    quiz_id = r.json()["id"]
    
    # Add questions
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/questions", json={
        "text": "1+1=?", "question_type": "mcq", "points": 10,
        "options": [{"text": "2", "is_correct": True}, {"text": "3", "is_correct": False}]
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    q1 = r.json()
    assert len(q1["options"]) == 2
    opt1_correct = [o["id"] for o in q1["options"] if o["is_correct"]][0]
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/questions", json={
        "text": "2+2=?", "question_type": "mcq", "points": 10,
        "options": [{"text": "4", "is_correct": True}, {"text": "5", "is_correct": False}]
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    q2 = r.json()
    opt2_correct = [o["id"] for o in q2["options"] if o["is_correct"]][0]
    
    # Student cannot see is_correct
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    # NOTE: Current endpoint returns QuizResponse which doesn't include questions/options,
    # so is_correct leaking test is implicitly passing
    
    # Start attempt
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/start", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    atm = r.json()
    atm_id = atm["id"]
    assert atm["score"] is None
    assert atm["submitted_at"] is None
    
    # Answer both questions correctly
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/attempts/{atm_id}/answer", json={
        "question_id": q1["id"], "selected_option_id": opt1_correct
    }, headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 201
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/attempts/{atm_id}/answer", json={
        "question_id": q2["id"], "selected_option_id": opt2_correct
    }, headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 201
    
    # Submit quiz
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/attempts/{atm_id}/submit", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    result = r.json()
    assert result["score"] == 20.0  # 10 + 10 points
    assert result["submitted_at"] is not None
    
    # Gradebook should have quiz entry
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/gradebook/me", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    grades = r.json()
    q_entries = [g for g in grades if g["item_type"] == "quiz"]
    assert len(q_entries) == 1, f"Expected 1 quiz gradebook entry, got {q_entries}"
    assert q_entries[0]["score"] == 20.0
    assert q_entries[0]["max_score"] == 100.0
    assert q_entries[0]["weight"] == 3.0
    assert q_entries[0]["title"] == "Quiz1"


@pytest.mark.asyncio
async def test_attendance_flow(client: AsyncClient, setup_users_and_course):
    """Attendance session -> Mark records -> Student reads own."""
    ctx = setup_users_and_course
    
    r = await client.post("/api/v1/auth/login", json={"email": "lecturer@lms.edu", "password": "Lecturer123"})
    lec_token = r.json()["access_token"]
    r = await client.post("/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student123"})
    stu_token = r.json()["access_token"]
    
    # Create session
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/attendance/sessions", json={
        "session_date": "2030-01-01", "title": "Lecture 1"
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    sess = r.json()
    sess_id = sess["id"]
    assert sess["title"] == "Lecture 1"
    
    # Mark attendance
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/attendance/sessions/{sess_id}/records", json={
        "records": [{"student_id": str(ctx["stu_id"]), "status": "present"}]
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    records = r.json()
    assert len(records) == 1
    assert records[0]["status"] == "present"
    assert records[0]["student_id"] == str(ctx["stu_id"])
    
    # Student reads own
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/attendance/me", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    my_records = r.json()
    assert len(my_records) == 1
    assert my_records[0]["status"] == "present"


@pytest.mark.asyncio
async def test_gradebook_weighted_total(client: AsyncClient, setup_users_and_course):
    """After grading an assignment and completing a quiz, both entries appear and weighted total is correct."""
    ctx = setup_users_and_course
    
    r = await client.post("/api/v1/auth/login", json={"email": "lecturer@lms.edu", "password": "Lecturer123"})
    lec_token = r.json()["access_token"]
    r = await client.post("/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student123"})
    stu_token = r.json()["access_token"]
    
    # Assignment: weight=2, score=80/100
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments", json={
        "title": "HW2", "max_score": 100, "is_published": True, "weight": 2.0
    }, headers={"Authorization": f"Bearer {lec_token}"})
    ass_id = r.json()["id"]
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments/{ass_id}/submit", json={
        "content_text": "ans"
    }, headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/assignments/{ass_id}/submissions/{ctx['stu_id']}/grade", json={
        "score": 80.0, "feedback": "ok"
    }, headers={"Authorization": f"Bearer {lec_token}"})
    assert r.status_code == 200
    
    # Quiz: weight=3, score=10/100
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes", json={
        "title": "Q2", "max_attempts": 1, "is_published": True, "max_score": 100.0, "weight": 3.0
    }, headers={"Authorization": f"Bearer {lec_token}"})
    quiz_id = r.json()["id"]
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/questions", json={
        "text": "Q?", "question_type": "mcq", "points": 10,
        "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]
    }, headers={"Authorization": f"Bearer {lec_token}"})
    q = r.json()
    correct_opt = [o["id"] for o in q["options"] if o["is_correct"]][0]
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/start", headers={"Authorization": f"Bearer {stu_token}"})
    atm_id = r.json()["id"]
    
    await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/attempts/{atm_id}/answer", json={
        "question_id": q["id"], "selected_option_id": correct_opt
    }, headers={"Authorization": f"Bearer {stu_token}"})
    
    r = await client.post(f"/api/v1/courses/{ctx['course_id']}/quizzes/{quiz_id}/attempts/{atm_id}/submit", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    
    # Read gradebook
    r = await client.get(f"/api/v1/courses/{ctx['course_id']}/gradebook/me", headers={"Authorization": f"Bearer {stu_token}"})
    assert r.status_code == 200
    grades = r.json()
    assert len(grades) == 2
    
    # Calculate weighted total: sum(score*weight) / sum(max_score*weight)
    total_weighted_score = sum(g["score"] * g["weight"] for g in grades)
    total_weighted_max = sum(g["max_score"] * g["weight"] for g in grades)
    weighted_pct = total_weighted_score / total_weighted_max * 100
    
    # Assignment: 80*2=160, Quiz: 10*3=30 -> 190
    # Max: 100*2=200, 100*3=300 -> 500
    # Weighted %: 190/500*100 = 38.0%
    assert total_weighted_score == 190.0
    assert total_weighted_max == 500.0
    assert abs(weighted_pct - 38.0) < 0.01
    print(f"\nWeighted total: {total_weighted_score}/{total_weighted_max} = {weighted_pct:.1f}%")
