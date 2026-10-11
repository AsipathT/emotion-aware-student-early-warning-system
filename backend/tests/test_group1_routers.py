import io
import csv
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient

from app.main import app
from app.core.database import get_db
from app.core.schema_mapping import (
    COL_ASSIGNMENTS,
    COL_ATTENDANCE_RECORDS,
    COL_ATTENDANCE_SESSIONS,
    COL_GRADEBOOK,
    COL_QUIZ_ATTEMPTS,
    COL_QUIZZES,
    COL_SUBMISSIONS,
)

TEST_MONGO_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "early_warning_group1_test"

# Strict safety guard: must end in _test
if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError("Test database name must strictly end in '_test'")

@pytest_asyncio.fixture
async def test_db():
    motor_client = AsyncIOMotorClient(TEST_MONGO_URI)
    db = motor_client[TEST_DB_NAME]
    await motor_client.drop_database(TEST_DB_NAME)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield db

    await motor_client.drop_database(TEST_DB_NAME)
    motor_client.close()


@pytest_asyncio.fixture
async def ac(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client_instance:
        yield client_instance


@pytest.mark.asyncio
async def test_group1_features_comprehensive(ac, test_db):
    # ── 1. Setup Actors ────────────────────────────────────────────────────────
    # Lecturer 1 (Course Owner)
    await ac.post("/api/v1/auth/register", json={"email": "lec1@lms.edu", "password": "Password1", "full_name": "Lecturer One", "role": "lecturer"})
    res_l1 = await ac.post("/api/v1/auth/login", json={"email": "lec1@lms.edu", "password": "Password1"})
    l1_token = res_l1.json()["access_token"]
    l1_headers = {"Authorization": f"Bearer {l1_token}"}

    # Lecturer 2 (Other Course Instructor)
    await ac.post("/api/v1/auth/register", json={"email": "lec2@lms.edu", "password": "Password1", "full_name": "Lecturer Two", "role": "lecturer"})
    res_l2 = await ac.post("/api/v1/auth/login", json={"email": "lec2@lms.edu", "password": "Password1"})
    l2_token = res_l2.json()["access_token"]
    l2_headers = {"Authorization": f"Bearer {l2_token}"}

    # Counsellor (Read-only)
    await ac.post("/api/v1/auth/register", json={"email": "counsellor@lms.edu", "password": "Password1", "full_name": "Counsellor C", "role": "counsellor"})
    res_c = await ac.post("/api/v1/auth/login", json={"email": "counsellor@lms.edu", "password": "Password1"})
    c_token = res_c.json()["access_token"]
    c_headers = {"Authorization": f"Bearer {c_token}"}

    # Enrolled Student (Stu 1)
    res_s1_reg = await ac.post("/api/v1/auth/register", json={"email": "stu1@lms.edu", "password": "Password1", "full_name": "Enrolled Stu", "role": "student"})
    stu1_id = res_s1_reg.json()["id"]
    res_s1 = await ac.post("/api/v1/auth/login", json={"email": "stu1@lms.edu", "password": "Password1"})
    s1_token = res_s1.json()["access_token"]
    s1_headers = {"Authorization": f"Bearer {s1_token}"}

    # Unenrolled Student (Stu 2)
    res_s2_reg = await ac.post("/api/v1/auth/register", json={"email": "stu2@lms.edu", "password": "Password1", "full_name": "Unenrolled Stu", "role": "student"})
    stu2_id = res_s2_reg.json()["id"]
    res_s2 = await ac.post("/api/v1/auth/login", json={"email": "stu2@lms.edu", "password": "Password1"})
    s2_token = res_s2.json()["access_token"]
    s2_headers = {"Authorization": f"Bearer {s2_token}"}

    # ── 2. Create Course and Module ───────────────────────────────────────────
    res_course = await ac.post("/api/v1/courses", json={"title": "Data Structures CS201", "is_published": True}, headers=l1_headers)
    assert res_course.status_code == 201
    course_id = res_course.json()["id"]

    # Enroll Stu 1 in course
    await test_db.enrollments.insert_one({
        "_id": str(uuid.uuid4()),
        "course_id": course_id,
        "student_id": stu1_id,
        "status": "active",
    })

    # Add Module with legacy payload (Feature 8)
    res_mod = await ac.post(f"/api/v1/courses/{course_id}/modules", json={
        "title": "Week 1: Trees",
        "sequence_order": 1,
        "content_payload": {"legacy_format_blob": True, "raw_note": "Unstructured binary data"}
    }, headers=l1_headers)
    assert res_mod.status_code == 201
    module_id = res_mod.json()["id"]

    # ── 3. Feature 8: Course Content & Block Validation ───────────────────────
    # GET module content page: legacy payload returned unchanged
    res_get_mod = await ac.get(f"/api/v1/courses/{course_id}/modules/{module_id}", headers=s1_headers)
    assert res_get_mod.status_code == 200
    assert res_get_mod.json()["content_payload"]["legacy_format_blob"] is True

    # Lecturer 2 (not course owner) attempts to PATCH module -> 403 Forbidden
    res_l2_patch = await ac.patch(f"/api/v1/courses/{course_id}/modules/{module_id}", json={
        "content_payload": {"blocks": [{"type": "text", "body": "Hacked content"}]}
    }, headers=l2_headers)
    assert res_l2_patch.status_code == 403

    # Lecturer 1 submits invalid blocks -> 422 Unprocessable Entity
    res_invalid_patch = await ac.patch(f"/api/v1/courses/{course_id}/modules/{module_id}", json={
        "content_payload": {"blocks": [{"type": "unknown_format", "data": "bad"}]}
    }, headers=l1_headers)
    assert res_invalid_patch.status_code == 422

    # Lecturer 1 submits valid blocks -> 200 OK
    valid_blocks = [
        {"type": "text", "body": "# Binary Search Trees\nDefinition and operations."},
        {"type": "video", "url": "https://video.lms.edu/bst.mp4", "title": "Tree Traversal"},
        {"type": "resource", "url": "https://cdn.lms.edu/trees.pdf", "title": "Slides", "mime_type": "application/pdf"}
    ]
    res_valid_patch = await ac.patch(f"/api/v1/courses/{course_id}/modules/{module_id}", json={
        "content_payload": {"blocks": valid_blocks}
    }, headers=l1_headers)
    assert res_valid_patch.status_code == 200
    assert len(res_valid_patch.json()["content_payload"]["blocks"]) == 3

    # ── 4. Feature 10: Assignments RBAC & Submission ──────────────────────────
    due_past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    res_a = await ac.post(f"/api/v1/courses/{course_id}/assignments", json={
        "title": "Assignment 1: BST Implementation",
        "max_score": 100.0,
        "weight": 0.4,
        "is_published": True,
        "due_at": due_past
    }, headers=l1_headers)
    assert res_a.status_code == 201
    aid = res_a.json()["id"]

    # Lecturer of another course gets 403 on grading
    res_l2_grade = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submissions/{stu1_id}/grade", json={"score": 80.0}, headers=l2_headers)
    assert res_l2_grade.status_code == 403

    # Unenrolled student gets 403 on submit
    res_unenrolled_sub = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submit", json={"content_text": "My code"}, headers=s2_headers)
    assert res_unenrolled_sub.status_code == 403

    # Enrolled student submits: late flag true, delay_days >= 3
    res_sub = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submit", json={"content_text": "Valid code"}, headers=s1_headers)
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["is_late"] is True
    assert sub_data["delay_days"] >= 3

    # Resubmission before grading: allowed
    res_resub = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submit", json={"content_text": "Updated code"}, headers=s1_headers)
    assert res_resub.status_code == 200

    # Student cannot read another student's submissions list
    res_read_forbidden = await ac.get(f"/api/v1/courses/{course_id}/assignments/{aid}/submissions", headers=s2_headers)
    assert res_read_forbidden.status_code == 403

    # Grading creates gradebook entry
    res_grade = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submissions/{stu1_id}/grade", json={"score": 80.0, "feedback": "Well done"}, headers=l1_headers)
    assert res_grade.status_code == 200

    # Re-grading updates, does NOT duplicate
    res_regrade = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submissions/{stu1_id}/grade", json={"score": 80.0, "feedback": "Final"}, headers=l1_headers)
    assert res_regrade.status_code == 200
    gb_count = await test_db[COL_GRADEBOOK].count_documents({"course_id": course_id, "student_id": stu1_id, "item_id": aid})
    assert gb_count == 1

    # Resubmission after grading: 409 Conflict
    res_after_grade = await ac.post(f"/api/v1/courses/{course_id}/assignments/{aid}/submit", json={"content_text": "Late try"}, headers=s1_headers)
    assert res_after_grade.status_code == 409

    # ── 5. Feature 11: Quizzes & Auto-grading Hand-computed Case ──────────────
    q1_opt_correct = str(uuid.uuid4())
    q1_opt_wrong = str(uuid.uuid4())
    q2_opt_correct = str(uuid.uuid4())
    q2_opt_wrong = str(uuid.uuid4())

    quiz_payload = {
        "title": "Quiz 1: Trees and Graphs",
        "max_score": 100.0,
        "weight": 0.6,
        "is_published": True,
        "max_attempts": 2,
        "questions": [
            {
                "id": "q1",
                "text": "What is the time complexity of searching a balanced BST?",
                "question_type": "mcq",
                "points": 2.0,
                "options": [
                    {"id": q1_opt_correct, "text": "O(log N)", "is_correct": True},
                    {"id": q1_opt_wrong, "text": "O(N^2)", "is_correct": False}
                ]
            },
            {
                "id": "q2",
                "text": "A tree can contain circular cycles.",
                "question_type": "true_false",
                "points": 3.0,
                "options": [
                    {"id": q2_opt_wrong, "text": "True", "is_correct": False},
                    {"id": q2_opt_correct, "text": "False", "is_correct": True}
                ]
            }
        ]
    }
    res_quiz = await ac.post(f"/api/v1/courses/{course_id}/quizzes", json=quiz_payload, headers=l1_headers)
    assert res_quiz.status_code == 201
    quiz_id = res_quiz.json()["id"]

    # Student views quiz: verify is_correct is NEVER leaked!
    res_stu_quiz = await ac.get(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}", headers=s1_headers)
    assert res_stu_quiz.status_code == 200
    for q in res_stu_quiz.json()["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt

    # Unenrolled student attempt -> 403
    res_unenrolled_att = await ac.post(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts", headers=s2_headers)
    assert res_unenrolled_att.status_code == 403

    # Enrolled student starts attempt 1
    res_att1 = await ac.post(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts", headers=s1_headers)
    assert res_att1.status_code == 201
    att1_id = res_att1.json()["id"]

    # Submit Attempt 1 with: Q1 correct (+2.0 points), Q2 wrong (+0.0 points)
    # Total points possible = 5.0. Earned = 2.0. Hand-computed score = (2.0 / 5.0) * 100.0 = 40.0
    res_sub_att1 = await ac.post(
        f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts/{att1_id}/submit",
        json={"answers": {"q1": q1_opt_correct, "q2": q2_opt_wrong}},
        headers=s1_headers
    )
    assert res_sub_att1.status_code == 200
    assert res_sub_att1.json()["score"] == 40.0
    assert res_sub_att1.json()["earned_points"] == 2.0
    assert res_sub_att1.json()["total_possible_points"] == 5.0

    # Start Attempt 2 (within max_attempts = 2)
    res_att2 = await ac.post(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts", headers=s1_headers)
    assert res_att2.status_code == 201
    att2_id = res_att2.json()["id"]

    # Submit Attempt 2 with both correct: (5.0 / 5.0) * 100.0 = 100.0
    res_sub_att2 = await ac.post(
        f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts/{att2_id}/submit",
        json={"answers": {"q1": q1_opt_correct, "q2": q2_opt_correct}},
        headers=s1_headers
    )
    assert res_sub_att2.status_code == 200
    assert res_sub_att2.json()["score"] == 100.0

    # Attempt 3: Max attempts reached -> 400 Bad Request
    res_att3 = await ac.post(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts", headers=s1_headers)
    assert res_att3.status_code == 400
    assert "Maximum attempts" in res_att3.json()["detail"]

    # ── 6. Feature 12: Gradebook Grid & Score So Far Hand-computed Case ───────
    # Current Gradebook State for Stu 1:
    # Item 1 (Assignment 1): score = 80.0, max_score = 100.0, weight = 0.4.
    #   -> weighted points = (80 / 100) * 0.4 = 0.32
    # Item 2 (Quiz 1): score = 100.0, max_score = 100.0, weight = 0.6.
    #   -> weighted points = (100 / 100) * 0.6 = 0.60
    # Total weighted points = 0.32 + 0.60 = 0.92
    # Total weight = 0.4 + 0.6 = 1.0
    # score_so_far = (0.92 / 1.0) * 100 = 92.0%
    res_gb = await ac.get(f"/api/v1/courses/{course_id}/gradebook", headers=l1_headers)
    assert res_gb.status_code == 200
    grid = res_gb.json()
    stu_record = next(s for s in grid["students"] if s["student_id"] == stu1_id)
    assert stu_record["weighted_total"] == 0.92
    assert stu_record["score_so_far"] == 92.0

    # Student own view
    res_my_gb = await ac.get(f"/api/v1/courses/{course_id}/gradebook/me", headers=s1_headers)
    assert res_my_gb.status_code == 200
    assert res_my_gb.json()["weighted_total"] == 0.92
    assert res_my_gb.json()["score_so_far"] == 92.0

    # Counsellor read-only view: 200 OK
    res_c_gb = await ac.get(f"/api/v1/courses/{course_id}/gradebook", headers=c_headers)
    assert res_c_gb.status_code == 200

    # Counsellor cannot write manual grades: 403 Forbidden
    res_c_write = await ac.post(f"/api/v1/courses/{course_id}/gradebook/manual", json={
        "student_id": stu1_id,
        "title": "Participation",
        "score": 10.0,
        "max_score": 10.0,
        "weight": 0.1
    }, headers=c_headers)
    assert res_c_write.status_code == 403

    # CSV Export: verify header and rows
    res_csv = await ac.get(f"/api/v1/courses/{course_id}/gradebook/csv", headers=l1_headers)
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    csv_reader = csv.reader(io.StringIO(res_csv.text))
    rows = list(csv_reader)
    assert rows[0] == ["Student ID", "Student Name", "Item Type", "Item Title", "Score", "Max Score", "Weight", "Recorded At"]
    assert len(rows) >= 3  # Header + 2 grade items

    # ── 7. Feature 13: Attendance Sessions, Bulk Mark & Hand-computed Rate ───
    # Create 4 Sessions
    now = datetime.now(timezone.utc)
    s_ids = []
    for i in range(1, 5):
        s_res = await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions", json={
            "title": f"Lab Session {i}",
            "session_date": (now + timedelta(days=i)).isoformat()
        }, headers=l1_headers)
        assert s_res.status_code == 201
        s_ids.append(s_res.json()["id"])

    # Mark attendance for Session 1, 2, 3, 4:
    # Session 1: present
    # Session 2: late
    # Session 3: absent
    # Session 4: excused
    await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[0]}/records", json={"records": [{"student_id": stu1_id, "status": "present"}]}, headers=l1_headers)
    await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[1]}/records", json={"records": [{"student_id": stu1_id, "status": "late"}]}, headers=l1_headers)
    await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[2]}/records", json={"records": [{"student_id": stu1_id, "status": "absent"}]}, headers=l1_headers)
    await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[3]}/records", json={"records": [{"student_id": stu1_id, "status": "excused"}]}, headers=l1_headers)

    # Hand-computed rate: 4 total sessions, attended (present + late) = 2. Rate = (2 / 4) * 100 = 50.0%
    res_my_att = await ac.get(f"/api/v1/courses/{course_id}/attendance/me", headers=s1_headers)
    assert res_my_att.status_code == 200
    assert res_my_att.json()["total_sessions"] == 4
    assert res_my_att.json()["attended_sessions"] == 2
    assert res_my_att.json()["attendance_rate"] == 50.0

    # Re-marking Session 3 as 'present' updates existing record (no duplication):
    res_re_mark = await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[2]}/records", json={"records": [{"student_id": stu1_id, "status": "present"}]}, headers=l1_headers)
    assert res_re_mark.status_code == 200
    rec_count = await test_db[COL_ATTENDANCE_RECORDS].count_documents({"session_id": s_ids[2], "student_id": stu1_id})
    assert rec_count == 1

    # New attendance rate: attended 3/4 = 75.0%
    res_updated_att = await ac.get(f"/api/v1/courses/{course_id}/attendance/me", headers=s1_headers)
    assert res_updated_att.json()["attended_sessions"] == 3
    assert res_updated_att.json()["attendance_rate"] == 75.0

    # Counsellor cannot write attendance records: 403 Forbidden
    res_c_att_write = await ac.post(f"/api/v1/courses/{course_id}/attendance/sessions/{s_ids[0]}/records", json={"records": [{"student_id": stu1_id, "status": "present"}]}, headers=c_headers)
    assert res_c_att_write.status_code == 403

    # Counsellor / Lecturer reads attendance summary
    res_att_sum = await ac.get(f"/api/v1/courses/{course_id}/attendance/summary", headers=c_headers)
    assert res_att_sum.status_code == 200
    assert res_att_sum.json()["total_sessions"] == 4
    assert len(res_att_sum.json()["students"]) == 1
    assert res_att_sum.json()["students"][0]["attendance_rate"] == 75.0

    # ── 8. Safety Verification: Strict Platform Owner Collections Untouched ──
    # The operational routers must NOT have touched his collections:
    assert await test_db.assignments.count_documents({}) == 0
    assert await test_db.submissions.count_documents({}) == 0
    assert await test_db.quizzes.count_documents({}) == 0
    assert await test_db.quiz_attempts.count_documents({}) == 0
    assert await test_db.grades.count_documents({}) == 0
    assert await test_db.attendance.count_documents({}) == 0

    # Must strictly have written to our operational lms_* collections:
    assert await test_db[COL_ASSIGNMENTS].count_documents({}) == 1
    assert await test_db[COL_SUBMISSIONS].count_documents({}) == 1
    assert await test_db[COL_QUIZZES].count_documents({}) == 1
    assert await test_db[COL_QUIZ_ATTEMPTS].count_documents({}) == 2
    assert await test_db[COL_GRADEBOOK].count_documents({}) == 2
    assert await test_db[COL_ATTENDANCE_SESSIONS].count_documents({}) == 4
    assert await test_db[COL_ATTENDANCE_RECORDS].count_documents({}) == 4
