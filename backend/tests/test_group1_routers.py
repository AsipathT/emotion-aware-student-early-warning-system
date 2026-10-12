"""
backend/tests/test_group1_routers.py

Modular integration tests for Group 1 LMS features:
  - Feature 8: Course Content & Modules (embedded array updates, validation, immutability)
  - Feature 10: Assignment Management & Grading
  - Feature 11: Quizzes & Question Answering
  - Feature 12: Gradebook & CSV Exports
  - Feature 13: Attendance Sessions & Records
  - RBAC & Cross-student Privacy
  - Feature 2/5: Enrollment & Privacy PID Resolution
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.core.privacy import pseudonymize, is_valid_pid
from app.core.schema_mapping import (
    COL_ASSIGNMENTS,
    COL_SUBMISSIONS,
    COL_QUIZZES,
    COL_QUIZ_ATTEMPTS,
    COL_GRADEBOOK,
    COL_ATTENDANCE_SESSIONS,
    COL_ATTENDANCE_RECORDS,
    CANONICAL_COURSES,
    CANONICAL_ENROLMENTS,
    CANONICAL_ENROLLMENTS,
    check_student_enrolled,
)

TEST_MONGO_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "early_warning_group1_test"

# Strict safety guard: enforce database name ends in _test
if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError("Test database name must end in '_test'")


@pytest_asyncio.fixture
async def test_db():
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(TEST_MONGO_URI)
    db = client[TEST_DB_NAME]
    await client.drop_database(TEST_DB_NAME)

    print(f"\n[DB HYGIENE] Test is executing on isolated database: {db.name}")

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield db

    await client.drop_database(TEST_DB_NAME)
    client.close()


@pytest_asyncio.fixture
async def async_client(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _register_and_login(ac: AsyncClient, email: str, role: str) -> tuple[dict, str]:
    res_reg = await ac.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": f"User {role}", "role": role},
    )
    user_id = res_reg.json()["id"]
    res_login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = res_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


# ── Feature 8: Course Content & Modules ───────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_8_course_content_modules(async_client, test_db):
    """
    Feature 8: Verifies module GET/PATCH on courses with embedded modules.
    Asserts:
      1. Courses validator with additionalProperties: False accepts the document.
      2. Editing module 1's content_payload leaves module 2 and course fields unchanged.
      3. Block validator enforces supported block types ('text', 'video', 'resource').
    """
    # 1. Apply MongoDB course validator with additionalProperties: False and modules array
    course_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["course_id", "title"],
            "additionalProperties": False,
            "properties": {
                "_id": {"bsonType": ["string", "objectId"]},
                "course_id": {"bsonType": "string"},
                "title": {"bsonType": "string"},
                "description": {"bsonType": ["string", "null"]},
                "lecturer_id": {"bsonType": ["string", "null"]},
                "is_published": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "schema_version": {"bsonType": ["int", "long"]},
                "source_version": {"bsonType": "string"},
                "ingested_at": {"bsonType": "date"},
                "modules": {
                    "bsonType": "array",
                    "items": {"bsonType": "object"},
                },
            },
        }
    }
    await test_db.command({"create": CANONICAL_COURSES, "validator": course_validator})

    lec_headers, lec_id = await _register_and_login(async_client, "lec_f8@sliit.edu", "lecturer")

    cid = str(uuid.uuid4())
    mid_1 = str(uuid.uuid4())
    mid_2 = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Initial course with 2 embedded modules
    course_doc = {
        "_id": cid,
        "course_id": cid,
        "title": "Data Structures & Algorithms",
        "description": "CS201 Core Course",
        "lecturer_id": lec_id,
        "is_published": True,
        "created_at": now,
        "updated_at": now,
        "modules": [
            {
                "_id": mid_1,
                "id": mid_1,
                "course_id": cid,
                "title": "Module 1: Arrays",
                "content_payload": {"blocks": [{"type": "text", "body": "Initial Array notes"}]},
                "sequence_order": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": mid_2,
                "id": mid_2,
                "course_id": cid,
                "title": "Module 2: Linked Lists",
                "content_payload": {"blocks": [{"type": "text", "body": "Initial Linked List notes"}]},
                "sequence_order": 2,
                "created_at": now,
                "updated_at": now,
            },
        ],
    }
    await test_db[CANONICAL_COURSES].insert_one(course_doc)

    # 2. PATCH module 1 content_payload
    updated_payload = {
        "title": "Module 1: Advanced Arrays",
        "content_payload": {
            "blocks": [
                {"type": "text", "body": "Updated dynamic arrays and sliding window"},
                {"type": "video", "title": "Array Lecture Video", "url": "https://cdn.lms.edu/arrays.mp4", "duration_seconds": 900},
                {"type": "resource", "url": "https://cdn.lms.edu/sheet.pdf", "title": "Cheatsheet", "mime_type": "application/pdf"},
            ]
        },
    }
    res_patch = await async_client.patch(
        f"/api/v1/courses/{cid}/modules/{mid_1}",
        json=updated_payload,
        headers=lec_headers,
    )
    assert res_patch.status_code == 200, res_patch.text
    patched_module = res_patch.json()
    assert patched_module["title"] == "Module 1: Advanced Arrays"
    assert len(patched_module["content_payload"]["blocks"]) == 3

    # 3. Verify in database: module 1 changed, module 2 and course fields completely unchanged
    stored_course = await test_db[CANONICAL_COURSES].find_one({"_id": cid})
    assert stored_course["title"] == "Data Structures & Algorithms"  # unchanged
    assert stored_course["description"] == "CS201 Core Course"  # unchanged
    assert stored_course["lecturer_id"] == lec_id  # unchanged
    assert len(stored_course["modules"]) == 2

    m1_db = next(m for m in stored_course["modules"] if m["_id"] == mid_1)
    m2_db = next(m for m in stored_course["modules"] if m["_id"] == mid_2)

    assert m1_db["title"] == "Module 1: Advanced Arrays"
    assert m1_db["content_payload"]["blocks"][0]["body"] == "Updated dynamic arrays and sliding window"
    # Module 2 remains intact
    assert m2_db["title"] == "Module 2: Linked Lists"
    assert m2_db["content_payload"]["blocks"][0]["body"] == "Initial Linked List notes"

    # 4. Verify block validation fails on invalid block type (e.g. 'audio')
    invalid_patch = {
        "content_payload": {"blocks": [{"type": "audio", "url": "https://cdn.lms.edu/podcast.mp3"}]}
    }
    res_bad = await async_client.patch(
        f"/api/v1/courses/{cid}/modules/{mid_1}",
        json=invalid_patch,
        headers=lec_headers,
    )
    assert res_bad.status_code == 422


# ── Feature 10: Assignments & Submissions ─────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_10_assignments_lifecycle(async_client, test_db):
    """
    Feature 10: Tests assignments creation, submissions, late penalties, and gradebook syncing.
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_f10@sliit.edu", "lecturer")
    stu_headers, stu_id = await _register_and_login(async_client, "stu_f10@sliit.edu", "student")

    res_c = await async_client.post("/api/v1/courses", json={"title": "Assignment Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    # Enroll student in canonical enrollments
    await test_db[CANONICAL_ENROLLMENTS].insert_one({
        "_id": str(uuid.uuid4()), "course_id": cid, "student_id": stu_id, "status": "active"
    })

    # Create assignment with past due_date to test late delay
    past_due = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assign_payload = {
        "title": "Lab 1: Recursion",
        "description": "Submit repo link",
        "max_score": 100.0,
        "weight": 0.15,
        "due_at": past_due,
        "is_published": True,
    }
    res_a = await async_client.post(f"/api/v1/courses/{cid}/assignments", json=assign_payload, headers=lec_headers)
    assert res_a.status_code == 201
    aid = res_a.json()["id"]

    # Student submits -> is_late True, delay_days >= 3
    res_sub = await async_client.post(
        f"/api/v1/courses/{cid}/assignments/{aid}/submit",
        json={"content_text": "https://github.com/stu/recursion"},
        headers=stu_headers,
    )
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["is_late"] is True
    assert sub_data["delay_days"] >= 3

    # Lecturer grades -> syncs to lms_gradebook
    res_grade = await async_client.post(
        f"/api/v1/courses/{cid}/assignments/{aid}/submissions/{stu_id}/grade",
        json={"score": 88.0, "feedback": "Well structured solution"},
        headers=lec_headers,
    )
    assert res_grade.status_code == 200

    gb_item = await test_db[COL_GRADEBOOK].find_one({"course_id": cid, "student_id": stu_id, "item_id": aid})
    assert gb_item is not None
    assert gb_item["score"] == 88.0
    assert gb_item["max_score"] == 100.0
    assert gb_item["weight"] == 0.15

    # Re-grade updates rather than creating a duplicate
    res_regrade = await async_client.post(
        f"/api/v1/courses/{cid}/assignments/{aid}/submissions/{stu_id}/grade",
        json={"score": 92.0, "feedback": "Extra credit awarded"},
        headers=lec_headers,
    )
    assert res_regrade.status_code == 200
    count_gb = await test_db[COL_GRADEBOOK].count_documents({"course_id": cid, "student_id": stu_id, "item_id": aid})
    assert count_gb == 1

    gb_updated = await test_db[COL_GRADEBOOK].find_one({"course_id": cid, "student_id": stu_id, "item_id": aid})
    assert gb_updated["score"] == 92.0

    # Student attempting to resubmit after grading receives 409 Conflict
    res_resub = await async_client.post(
        f"/api/v1/courses/{cid}/assignments/{aid}/submit",
        json={"content_text": "Updated repo"},
        headers=stu_headers,
    )
    assert res_resub.status_code == 409


# ── Feature 11: Quizzes & Question Answering ──────────────────────────────────

@pytest.mark.asyncio
async def test_feature_11_quizzes_lifecycle(async_client, test_db):
    """
    Feature 11: Tests quiz creation, answer-stripping privacy, attempt taking, and auto-grading.
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_f11@sliit.edu", "lecturer")
    stu_headers, stu_id = await _register_and_login(async_client, "stu_f11@sliit.edu", "student")

    res_c = await async_client.post("/api/v1/courses", json={"title": "Quiz Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    await test_db[CANONICAL_ENROLLMENTS].insert_one({
        "_id": str(uuid.uuid4()), "course_id": cid, "student_id": stu_id, "status": "active"
    })

    # Lecturer creates quiz with questions & options embedded
    quiz_payload = {
        "title": "Quiz 1: Python Basics",
        "time_limit_minutes": 20,
        "max_score": 10.0,
        "weight": 0.1,
        "is_published": True,
        "max_attempts": 2,
        "questions": [
            {
                "id": "q1",
                "text": "Is Python interpreted?",
                "question_type": "true_false",
                "points": 5.0,
                "options": [
                    {"id": "opt1", "text": "True", "is_correct": True},
                    {"id": "opt2", "text": "False", "is_correct": False},
                ],
            },
            {
                "id": "q2",
                "text": "Which is an immutable type?",
                "question_type": "mcq",
                "points": 5.0,
                "options": [
                    {"id": "opt3", "text": "List", "is_correct": False},
                    {"id": "opt4", "text": "Tuple", "is_correct": True},
                ],
            },
        ],
    }
    res_q = await async_client.post(f"/api/v1/courses/{cid}/quizzes", json=quiz_payload, headers=lec_headers)
    assert res_q.status_code == 201
    qid = res_q.json()["id"]

    # Student GET quiz -> is_correct MUST NEVER BE LEAKED
    res_sget = await async_client.get(f"/api/v1/courses/{cid}/quizzes/{qid}", headers=stu_headers)
    assert res_sget.status_code == 200
    s_quiz = res_sget.json()
    for q in s_quiz["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt or opt["is_correct"] is None

    # Student starts attempt 1
    res_att = await async_client.post(f"/api/v1/courses/{cid}/quizzes/{qid}/attempts", headers=stu_headers)
    assert res_att.status_code == 201
    att_id = res_att.json()["id"]

    # Student submits answers (1 correct, 1 incorrect) -> 5.0 / 10.0
    submit_payload = {
        "answers": {
            "q1": "opt1",  # correct (+5.0)
            "q2": "opt3",  # incorrect List
        }
    }
    res_sub = await async_client.post(
        f"/api/v1/courses/{cid}/quizzes/{qid}/attempts/{att_id}/submit",
        json=submit_payload,
        headers=stu_headers,
    )
    assert res_sub.status_code == 200
    att_result = res_sub.json()
    assert att_result["score"] == 5.0
    assert att_result["max_score"] == 10.0

    # Auto-grading records to lms_gradebook
    gb_entry = await test_db[COL_GRADEBOOK].find_one({"course_id": cid, "student_id": stu_id, "item_id": qid})
    assert gb_entry is not None
    assert gb_entry["item_type"] == "quiz"
    assert gb_entry["score"] == 5.0


# ── Feature 12: Gradebook & CSV Exports ───────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_12_gradebook_and_csv(async_client, test_db):
    """
    Feature 12: Tests gradebook aggregation, score_so_far calculation, manual entries, and CSV download.
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_f12@sliit.edu", "lecturer")
    stu_headers, stu_id = await _register_and_login(async_client, "stu_f12@sliit.edu", "student")

    res_c = await async_client.post("/api/v1/courses", json={"title": "Gradebook Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    # Insert two grades:
    # 1. Assignment: 80 / 100, weight 0.2 -> (80/100)*0.2 = 0.16
    # 2. Quiz: 40 / 50, weight 0.3 -> (40/50)*0.3 = 0.24
    # Total weight = 0.5. Sum = 0.40. score_so_far = (0.40 / 0.5) * 100 = 80.0%
    now = datetime.now(timezone.utc)
    await test_db[COL_GRADEBOOK].insert_many([
        {
            "_id": str(uuid.uuid4()),
            "course_id": cid,
            "student_id": stu_id,
            "item_type": "assignment",
            "item_id": "a1",
            "title": "Assignment 1",
            "score": 80.0,
            "max_score": 100.0,
            "weight": 0.2,
            "recorded_at": now,
        },
        {
            "_id": str(uuid.uuid4()),
            "course_id": cid,
            "student_id": stu_id,
            "item_type": "quiz",
            "item_id": "q1",
            "title": "Quiz 1",
            "score": 40.0,
            "max_score": 50.0,
            "weight": 0.3,
            "recorded_at": now,
        },
    ])

    # Lecturer views gradebook
    res_gb = await async_client.get(f"/api/v1/courses/{cid}/gradebook", headers=lec_headers)
    assert res_gb.status_code == 200
    gb_data = res_gb.json()
    assert len(gb_data["students"]) == 1
    stu_summary = gb_data["students"][0]
    assert pytest.approx(stu_summary["score_so_far"], 0.01) == 80.0

    # Student views own gradebook
    res_me = await async_client.get(f"/api/v1/courses/{cid}/gradebook/me", headers=stu_headers)
    assert res_me.status_code == 200
    assert pytest.approx(res_me.json()["score_so_far"], 0.01) == 80.0

    # Lecturer manual adjustment
    manual_payload = {
        "student_id": stu_id,
        "title": "Midterm Exam",
        "score": 90.0,
        "max_score": 100.0,
        "weight": 0.5,
    }
    res_man = await async_client.post(f"/api/v1/courses/{cid}/gradebook/manual", json=manual_payload, headers=lec_headers)
    assert res_man.status_code in (200, 201)

    # CSV Download
    res_csv = await async_client.get(f"/api/v1/courses/{cid}/gradebook/csv", headers=lec_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Student ID,Student Name,Item Type,Item Title,Score,Max Score,Weight,Recorded At" in res_csv.text
    assert "Midterm Exam" in res_csv.text


# ── Feature 13: Attendance Sessions & Records ─────────────────────────────────

@pytest.mark.asyncio
async def test_feature_13_attendance_tracking(async_client, test_db):
    """
    Feature 13: Tests attendance session creation, bulk recording, re-mark updates, and attendance rate formula.
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_f13@sliit.edu", "lecturer")
    stu_headers, stu_id = await _register_and_login(async_client, "stu_f13@sliit.edu", "student")

    res_c = await async_client.post("/api/v1/courses", json={"title": "Attendance Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    # Student must be enrolled
    await test_db[CANONICAL_ENROLLMENTS].insert_one({
        "_id": str(uuid.uuid4()), "course_id": cid, "student_id": stu_id, "status": "active"
    })

    # Lecturer creates 2 sessions
    res_s1 = await async_client.post(
        f"/api/v1/courses/{cid}/attendance/sessions",
        json={"title": "Lecture 1", "session_date": datetime.now(timezone.utc).isoformat()},
        headers=lec_headers,
    )
    assert res_s1.status_code == 201
    sid1 = res_s1.json()["id"]

    res_s2 = await async_client.post(
        f"/api/v1/courses/{cid}/attendance/sessions",
        json={"title": "Lecture 2", "session_date": datetime.now(timezone.utc).isoformat()},
        headers=lec_headers,
    )
    assert res_s2.status_code == 201
    sid2 = res_s2.json()["id"]

    # Mark student 'present' in session 1, 'absent' in session 2
    await async_client.post(
        f"/api/v1/courses/{cid}/attendance/sessions/{sid1}/records",
        json={"records": [{"student_id": stu_id, "status": "present"}]},
        headers=lec_headers,
    )
    res_rec = await async_client.post(
        f"/api/v1/courses/{cid}/attendance/sessions/{sid2}/records",
        json={"records": [{"student_id": stu_id, "status": "absent", "notes": "Unexcused"}]},
        headers=lec_headers,
    )
    assert res_rec.status_code == 200
    assert res_rec.json()["records_count"] == 1

    # Student views attendance rate: 1 attended out of 2 total sessions -> 50.0%
    res_att_me = await async_client.get(f"/api/v1/courses/{cid}/attendance/me", headers=stu_headers)
    assert res_att_me.status_code == 200
    assert pytest.approx(res_att_me.json()["attendance_rate"], 0.01) == 50.0

    # Re-marking session 2 as 'present' updates existing record without duplicate
    records_update = {
        "records": [
            {"student_id": stu_id, "status": "present", "notes": "Medical excuse approved"}
        ]
    }
    res_rec2 = await async_client.post(
        f"/api/v1/courses/{cid}/attendance/sessions/{sid2}/records",
        json=records_update,
        headers=lec_headers,
    )
    assert res_rec2.status_code == 200

    count_records = await test_db[COL_ATTENDANCE_RECORDS].count_documents({"session_id": sid2, "student_id": stu_id})
    assert count_records == 1

    # Now attendance rate is 2 out of 2 -> 100.0%
    res_att_me2 = await async_client.get(f"/api/v1/courses/{cid}/attendance/me", headers=stu_headers)
    assert pytest.approx(res_att_me2.json()["attendance_rate"], 0.01) == 100.0


# ── RBAC & Cross-Student Privacy ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group1_rbac_and_cross_student_privacy(async_client, test_db):
    """
    Asserts cross-cutting RBAC constraints and student data isolation.
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_rbac@sliit.edu", "lecturer")
    stu1_headers, stu1_id = await _register_and_login(async_client, "stu1_rbac@sliit.edu", "student")
    stu2_headers, stu2_id = await _register_and_login(async_client, "stu2_rbac@sliit.edu", "student")
    counsellor_headers, _ = await _register_and_login(async_client, "couns_rbac@sliit.edu", "counsellor")

    res_c = await async_client.post("/api/v1/courses", json={"title": "RBAC Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    # 1. Unauthenticated requests get 401
    res_no_auth = await async_client.get(f"/api/v1/courses/{cid}/assignments")
    assert res_no_auth.status_code in (401, 403)

    # 2. Non-enrolled student gets 403 on assignment submit
    assign_payload = {
        "title": "Restricted Assignment",
        "max_score": 100.0,
        "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "is_published": True,
    }
    res_a = await async_client.post(f"/api/v1/courses/{cid}/assignments", json=assign_payload, headers=lec_headers)
    aid = res_a.json()["id"]

    res_sub_not_enrolled = await async_client.post(
        f"/api/v1/courses/{cid}/assignments/{aid}/submit",
        json={"content_text": "work"},
        headers=stu1_headers,
    )
    assert res_sub_not_enrolled.status_code == 403
    assert "Not enrolled" in res_sub_not_enrolled.json()["detail"]

    # Enroll stu1
    await test_db[CANONICAL_ENROLLMENTS].insert_one({
        "_id": str(uuid.uuid4()), "course_id": cid, "student_id": stu1_id, "status": "active"
    })
    await async_client.post(f"/api/v1/courses/{cid}/assignments/{aid}/submit", json={"content_text": "stu1 work"}, headers=stu1_headers)

    # 3. Student 2 cannot read Student 1's submission (list endpoint is lecturer only)
    res_read_other = await async_client.get(f"/api/v1/courses/{cid}/assignments/{aid}/submissions", headers=stu2_headers)
    assert res_read_other.status_code == 403

    # 4. Counsellor cannot post manual grade adjustments (read-only view)
    res_couns_post = await async_client.post(
        f"/api/v1/courses/{cid}/gradebook/manual",
        json={"student_id": stu1_id, "title": "Bonus", "score": 5.0, "max_score": 5.0, "weight": 0.05},
        headers=counsellor_headers,
    )
    assert res_couns_post.status_code == 403


# ── Feature 2/5: Enrollment & Privacy PID Resolution ──────────────────────────

@pytest.mark.asyncio
async def test_feature_2_enrollment_privacy_pid_resolution(async_client, test_db):
    """
    Demonstrates:
      1. Exact privacy function called: app.core.privacy.pseudonymize(student_id: str) -> str
      2. The platform owner's real enrollment endpoint POST /api/v1/enrollments/{course_id}
         writes strictly to 'enrollments' (with 'student_id': user.id).
      3. The computed PID STU_xxxxxxxx matches the canonical pseudonym algorithm.
      4. check_student_enrolled recognizes students in both 'enrolments' (by PID) and 'enrollments' (by student_id).
    """
    lec_headers, lec_id = await _register_and_login(async_client, "lec_enr@sliit.edu", "lecturer")
    stu_headers, stu_id = await _register_and_login(async_client, "stu_enr@sliit.edu", "student")

    res_c = await async_client.post("/api/v1/courses", json={"title": "Enrollment Test Course", "is_published": True}, headers=lec_headers)
    cid = res_c.json()["id"]

    # Call platform owner's REAL endpoint: POST /api/v1/enrollments/{course_id}
    res_enr = await async_client.post(f"/api/v1/enrollments/{cid}", headers=stu_headers)
    assert res_enr.status_code == 201

    # Verify which collection the owner's endpoint wrote to:
    enr_doc = await test_db[CANONICAL_ENROLLMENTS].find_one({"course_id": cid, "student_id": stu_id})
    assert enr_doc is not None, "Owner's endpoint writes to 'enrollments' collection"
    assert enr_doc["status"] == "active"

    # Confirm it DID NOT write to 'enrolments' (single 'l')
    enrolments_doc = await test_db[CANONICAL_ENROLMENTS].find_one({"course_id": cid})
    assert enrolments_doc is None, "Owner's endpoint writes strictly to 'enrollments', never 'enrolments'"

    # Compute PID using exact app.core.privacy.pseudonymize function
    pid = pseudonymize(stu_id)
    assert is_valid_pid(pid), f"PID '{pid}' must match format STU_[0-9a-fA-F]{{8}}"

    # Check student is recognized as enrolled via 'enrollments'
    is_enrolled_legacy = await check_student_enrolled(test_db, cid, uuid.UUID(stu_id))
    assert is_enrolled_legacy is True

    # Also test inserting into canonical 'enrolments' collection with PID (platform owner's ML Feature 25 format)
    cid_ml = str(uuid.uuid4())
    await test_db[CANONICAL_ENROLMENTS].insert_one({
        "_id": f"{pid}_{cid_ml}",
        "course_id": cid_ml,
        "pid": pid,
        "status": "active",
        "schema_version": 1,
    })
    is_enrolled_canonical = await check_student_enrolled(test_db, cid_ml, uuid.UUID(stu_id))
    assert is_enrolled_canonical is True
