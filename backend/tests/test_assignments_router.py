import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.core.database import get_db
from app.core.schema_mapping import (
    COL_ASSIGNMENTS,
    COL_GRADEBOOK,
    COL_SUBMISSIONS,
)
import uuid
from datetime import datetime, timezone, timedelta

TEST_MONGO_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "early_warning_test"

if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError("Test database name must end in '_test'")

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
async def async_client(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_assignments_strengthened_assertions(async_client, test_db):
    # Setup users
    res = await async_client.post("/api/v1/auth/register", json={"email": "lec@test.com", "password": "Password1", "full_name": "Lec", "role": "lecturer"})
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "lec@test.com", "password": "Password1"})
    lec_token = res_login.json()["access_token"]
    lec_headers = {"Authorization": f"Bearer {lec_token}"}
    
    res = await async_client.post("/api/v1/auth/register", json={"email": "stu1@test.com", "password": "Password1", "full_name": "Stu1", "role": "student"})
    stu1_id = res.json()["id"]
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "stu1@test.com", "password": "Password1"})
    stu1_token = res_login.json()["access_token"]
    stu1_headers = {"Authorization": f"Bearer {stu1_token}"}
    
    res2 = await async_client.post("/api/v1/auth/register", json={"email": "stu2@test.com", "password": "Password1", "full_name": "Stu2", "role": "student"})
    stu2_id = res2.json()["id"]
    res_login2 = await async_client.post("/api/v1/auth/login", json={"email": "stu2@test.com", "password": "Password1"})
    stu2_token = res_login2.json()["access_token"]
    stu2_headers = {"Authorization": f"Bearer {stu2_token}"}

    # Course
    res = await async_client.post("/api/v1/courses", json={"title": "Test Course", "is_published": True}, headers=lec_headers)
    course_id = res.json()["id"]

    # Enroll stu1
    await test_db.enrollments.insert_one({"_id": str(uuid.uuid4()), "course_id": course_id, "student_id": stu1_id, "role": "student", "status": "active"})

    # Assignment (past due for late testing)
    past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assignment_data = {"title": "A1", "max_score": 100, "weight": 0.5, "is_published": True, "due_at": past_date}
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments", json=assignment_data, headers=lec_headers)
    assert res.status_code == 201
    assignment_id = res.json()["id"]

    # Assertion 1: not-enrolled student gets 403 on submit
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submit", json={"content_text": "work"}, headers=stu2_headers)
    assert res.status_code == 403
    assert "Not enrolled" in res.json()["detail"]

    # Assertion 2: late submission has is_late=true and the correct delay_days
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submit", json={"content_text": "work"}, headers=stu1_headers)
    assert res.status_code == 200
    sub_data = res.json()
    assert sub_data["is_late"] is True
    assert sub_data["delay_days"] >= 2

    # Assertion 3: grading creates a lms_gradebook document with correct score, max_score, weight
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{stu1_id}/grade", json={"score": 85.0, "feedback": "Good job"}, headers=lec_headers)
    assert res.status_code == 200
    
    gb_entry = await test_db[COL_GRADEBOOK].find_one({"course_id": course_id, "student_id": stu1_id})
    assert gb_entry is not None
    assert gb_entry["score"] == 85.0
    assert gb_entry["max_score"] == 100.0
    assert gb_entry["weight"] == 0.5

    # Re-grading updates, does NOT duplicate
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{stu1_id}/grade", json={"score": 90.0, "feedback": "Revised"}, headers=lec_headers)
    assert res.status_code == 200
    gb_count = await test_db[COL_GRADEBOOK].count_documents({"course_id": course_id, "student_id": stu1_id})
    assert gb_count == 1
    gb_updated = await test_db[COL_GRADEBOOK].find_one({"course_id": course_id, "student_id": stu1_id})
    assert gb_updated["score"] == 90.0

    # Assertion 4: proves that it does NOT write into platform owner's strict collections
    assert await test_db.assignments.count_documents({}) == 0
    assert await test_db.submissions.count_documents({}) == 0
    assert await test_db.grades.count_documents({}) == 0

    # Proves it DOES write into lms_* operational collections
    assert await test_db[COL_ASSIGNMENTS].count_documents({}) == 1
    assert await test_db[COL_SUBMISSIONS].count_documents({}) == 1
    assert await test_db[COL_GRADEBOOK].count_documents({}) == 1

    # Assertion 5: no token gets 401 or 403
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments")
    assert res.status_code in (401, 403)
    
    # Assertion 6: a student cannot read another student's submissions list
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions", headers=stu2_headers)
    assert res.status_code == 403

    # Student reads own submission
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/my-submission", headers=stu1_headers)
    assert res.status_code == 200
    assert res.json()["score"] == 90.0
