import io
import os
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient

from app.main import app
from app.core.database import get_db

TEST_MONGO_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "early_warning_video_test"


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
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_video_management_and_10mb_limit(async_client, test_db):
    # 1. Register Lecturer
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "lec_vid@test.com", "password": "Password1", "full_name": "Dr. Lecturer", "role": "lecturer"},
    )
    assert res.status_code == 201
    lec_id = res.json()["id"]

    res_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "lec_vid@test.com", "password": "Password1"},
    )
    lec_token = res_login.json()["access_token"]
    lec_headers = {"Authorization": f"Bearer {lec_token}"}

    # 2. Register Student
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "stu_vid@test.com", "password": "Password1", "full_name": "Jane Student", "role": "student"},
    )
    assert res.status_code == 201

    res_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "stu_vid@test.com", "password": "Password1"},
    )
    stu_token = res_login.json()["access_token"]
    stu_headers = {"Authorization": f"Bearer {stu_token}"}

    # 3. Create Course (Published so student can enroll)
    course_res = await async_client.post(
        "/api/v1/courses",
        headers=lec_headers,
        json={"title": "Data Structures & Algorithms", "description": "Core computer science course", "is_published": True},
    )
    assert course_res.status_code == 201
    course_id = course_res.json()["id"]

    # Enroll student in course
    enroll_res = await async_client.post(
        f"/api/v1/enrollments/{course_id}",
        headers=stu_headers,
    )
    assert enroll_res.status_code == 201

    # 4. Attempt to upload a video larger than 10MB (e.g. 10.5 MB) -> Must be rejected with 400 Bad Request
    large_size = 10 * 1024 * 1024 + 500 * 1024  # 10.5 MB
    large_content = b"0" * large_size
    large_upload = await async_client.post(
        f"/api/v1/courses/{course_id}/videos",
        headers=lec_headers,
        data={"title": "Oversized Video", "description": "Too large"},
        files={"file": ("too_large.mp4", io.BytesIO(large_content), "video/mp4")},
    )
    assert large_upload.status_code == 400
    assert "exceeds maximum allowed size of 10MB" in large_upload.json()["detail"]

    # 5. Upload a valid video under 10MB (e.g. 50 KB dummy video content) -> Must succeed (201 Created)
    valid_content = b"FAKE_MP4_HEADER_DATA_" + b"x" * 50000
    valid_upload = await async_client.post(
        f"/api/v1/courses/{course_id}/videos",
        headers=lec_headers,
        data={"title": "Lecture 1: Intro to Big O", "description": "Asymptotic analysis"},
        files={"file": ("lecture1.mp4", io.BytesIO(valid_content), "video/mp4")},
    )
    assert valid_upload.status_code == 201
    video_data = valid_upload.json()
    video_id = video_data["id"]
    assert video_data["title"] == "Lecture 1: Intro to Big O"
    assert video_data["file_size"] == len(valid_content)

    # 6. List videos as student -> Allowed, returns video with initial 0 watch time
    list_res = await async_client.get(
        f"/api/v1/courses/{course_id}/videos",
        headers=stu_headers,
    )
    assert list_res.status_code == 200
    videos_list = list_res.json()
    assert len(videos_list) == 1
    assert videos_list[0]["id"] == video_id
    assert videos_list[0]["unique_viewers"] == 0
    assert videos_list[0]["total_watch_minutes"] == 0.0

    # 7. Student streams video
    stream_res = await async_client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=stu_headers,
    )
    assert stream_res.status_code == 200
    assert stream_res.content == valid_content

    # 8. Student sends watch progress heartbeat (e.g. watched 90 seconds)
    watch_res = await async_client.post(
        f"/api/v1/videos/{video_id}/watch",
        headers=stu_headers,
        json={"watched_seconds": 90.0, "current_time": 90.0, "completed": False},
    )
    assert watch_res.status_code == 200
    assert watch_res.json()["student_watch_seconds"] == 90.0
    assert watch_res.json()["student_watch_minutes"] == 1.5

    # 9. Lecturer views course videos -> should reflect 1 unique viewer and 1.5 minutes
    lec_list_res = await async_client.get(
        f"/api/v1/courses/{course_id}/videos",
        headers=lec_headers,
    )
    assert lec_list_res.status_code == 200
    lec_videos = lec_list_res.json()
    assert lec_videos[0]["unique_viewers"] == 1
    assert lec_videos[0]["total_watch_minutes"] == 1.5
    assert len(lec_videos[0]["viewers"]) == 1
    assert lec_videos[0]["viewers"][0]["student_name"] == "Jane Student"
    assert lec_videos[0]["viewers"][0]["total_watch_minutes"] == 1.5

    # 10. Lecturer deletes video
    del_res = await async_client.delete(
        f"/api/v1/courses/{course_id}/videos/{video_id}",
        headers=lec_headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify list is now empty
    empty_list = await async_client.get(
        f"/api/v1/courses/{course_id}/videos",
        headers=lec_headers,
    )
    assert len(empty_list.json()) == 0
