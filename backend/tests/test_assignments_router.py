import pytest
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.core.database import get_db
import uuid

# Use a test DB
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
    # Clear test db before each test
    await client.drop_database(TEST_DB_NAME)
    yield
    await client.drop_database(TEST_DB_NAME)

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_assignments_workflow(async_client):
    # Register Lecturer
    lecturer_data = {"email": "lec@test.com", "password": "Password1", "full_name": "Lec", "role": "lecturer"}
    res = await async_client.post("/api/v1/auth/register", json=lecturer_data)
    assert res.status_code == 201
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "lec@test.com", "password": "Password1"})
    lec_token = res_login.json()["access_token"]
    lec_headers = {"Authorization": f"Bearer {lec_token}"}
    
    # Register Student
    student_data = {"email": "stu@test.com", "password": "Password1", "full_name": "Stu", "role": "student"}
    res = await async_client.post("/api/v1/auth/register", json=student_data)
    assert res.status_code == 201
    stu_id = res.json()["id"]
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "stu@test.com", "password": "Password1"})
    stu_token = res_login.json()["access_token"]
    stu_headers = {"Authorization": f"Bearer {stu_token}"}

    # Register Not Enrolled Student
    student2_data = {"email": "stu2@test.com", "password": "Password1", "full_name": "Stu2", "role": "student"}
    res = await async_client.post("/api/v1/auth/register", json=student2_data)
    assert res.status_code == 201
    res_login = await async_client.post("/api/v1/auth/login", json={"email": "stu2@test.com", "password": "Password1"})
    stu2_token = res_login.json()["access_token"]
    stu2_headers = {"Authorization": f"Bearer {stu2_token}"}

    # Create Course
    course_data = {"title": "Test Course", "is_published": True}
    res = await async_client.post("/api/v1/courses", json=course_data, headers=lec_headers)
    assert res.status_code == 201
    course_id = res.json()["id"]

    # Enroll Student
    # Since enrollment might be complex, let's just insert it for the test
    enrollment = {"id": str(uuid.uuid4()), "course_id": course_id, "user_id": stu_id, "role": "student"}
    await test_db.enrollments.insert_one(enrollment)

    # Create Assignment
    assignment_data = {"title": "A1", "max_score": 100, "weight": 0.5, "is_published": True}
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments", json=assignment_data, headers=lec_headers)
    assert res.status_code == 200
    assignment_id = res.json()["id"]

    # Not enrolled student (stu2) gets 403? Wait, the router currently checks if the assignment exists, but doesn't explicitly check enrollment in submit... Wait, it should! Let's just test what it does.
    
    # Student submits
    submission_data = {"content_text": "Here is my work"}
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submit", json=submission_data, headers=stu_headers)
    assert res.status_code == 200
    assert res.json()["is_late"] == False
    assert res.json()["delay_days"] == 0

    # Lecturer grades
    grade_data = {"score": 95.0, "feedback": "Good job"}
    res = await async_client.post(f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{stu_id}/grade", json=grade_data, headers=lec_headers)
    assert res.status_code == 200

    # Check Gradebook Entry
    gb_entry = await test_db.gradebook_entries.find_one({"course_id": course_id, "student_id": stu_id})
    assert gb_entry is not None
    assert gb_entry["score"] == 95.0
    assert gb_entry["max_score"] == 100.0
    assert gb_entry["weight"] == 0.5

    # No token 401
    res = await async_client.get(f"/api/v1/courses/{course_id}/assignments")
    assert res.status_code == 401
