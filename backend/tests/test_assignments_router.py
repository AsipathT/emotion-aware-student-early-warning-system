import pytest
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.core.database import get_db
import uuid
from datetime import datetime, timezone, timedelta

TEST_MONGO_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "early_warning_test"

if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError("Test database name must end in '_test'")

client = AsyncIOMotorClient(TEST_MONGO_URI)
test_db = client[TEST_DB_NAME]

async def override_get_db():
    yield test_db

app.dependency_overrides[get_db] = override_get_db

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def clear_db():
    await client.drop_database(TEST_DB_NAME)
    yield
    await client.drop_database(TEST_DB_NAME)

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_assignments_strengthened_assertions(async_client):
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
    
    res = await async_client.post("/api/v1/auth/register", json={"email": "stu2@test.com", "password": "Password1", "full_name": "Stu2", "role": "student"})
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "stu2@test.com", "password": "Password1"})
    stu2_token = res_login.json()["access_token"]
    stu2_headers = {"Authorization": f"Bearer {stu2_token}"}

    # Course
    res = await async_client.post("/api/v1/courses", json={"title": "Test Course", "is_published": True}, headers=lec_headers)
    course_id = res.json()["id"]

    # Enroll stu1
    await test_db.enrollments.insert_one({"_id": str(uuid.uuid4()), "course_id": course_id, "student_id": stu1_id, "role": "student"})

    # Assignment (past due for late testing)
    past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assignment_data = {"title": "A1", "max_score": 100, "weight": 0.5, "is_published": True, "due_at": past_date}
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments", json=assignment_data, headers=lec_headers)
    assignment_id = res.json()["id"]

    # Assertion 1: not-enrolled student gets 403 on submit
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submit", json={"content_text": "work"}, headers=stu2_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "Not enrolled in this course"

    # Assertion 2: late submission has is_late=true and the correct delay_days
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submit", json={"content_text": "work"}, headers=stu1_headers)
    assert res.status_code == 200
    sub_data = res.json()
    assert sub_data["is_late"] == True
    assert sub_data["delay_days"] >= 2

    # Assertion 3: grading creates a gradebook_entries document with correct score, max_score, weight
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{stu1_id}/grade", json={"score": 85.0}, headers=lec_headers)
    assert res.status_code == 200
    
    gb_entry = await test_db.gradebook_entries.find_one({"course_id": course_id, "student_id": stu1_id})
    assert gb_entry is not None
    assert gb_entry["score"] == 85.0
    assert gb_entry["max_score"] == 100.0
    assert gb_entry["weight"] == 0.5

    # Assertion 4: no token gets 401
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments")
    assert res.status_code == 401
    
    # Assertion 5: a student cannot read another student's submission
    # Let's try to access the list endpoint as stu2 (a student). The endpoint requires LECTURER/ADMIN role.
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions", headers=stu2_headers)
    assert res.status_code == 403
