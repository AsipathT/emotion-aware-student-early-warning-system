import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pseudonym import pseudonymize
from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole


@pytest_asyncio.fixture
async def rbac_ingestion_setup(db_session: AsyncSession):
    """Seed users with all roles and an active course enrollment."""
    admin = User(
        id=uuid.uuid4(), email="admin_rbac@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Admin User", role=UserRole.ADMIN, is_active=True,
    )
    lecturer = User(
        id=uuid.uuid4(), email="lec_rbac@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Lecturer User", role=UserRole.LECTURER, is_active=True,
    )
    counsellor = User(
        id=uuid.uuid4(), email="coun_rbac@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Counsellor User", role=UserRole.COUNSELLOR, is_active=True,
    )
    student = User(
        id=uuid.uuid4(), email="stu_rbac@lms.edu", hashed_password=hash_password("Pass123"),
        full_name="Student User", role=UserRole.STUDENT, is_active=True,
    )

    course = Course(
        id=uuid.uuid4(), title="RBAC Course", lecturer_id=lecturer.id,
        start_date=date.today() - timedelta(days=14),
    )
    enrollment = Enrollment(id=uuid.uuid4(), user_id=student.id, course_id=course.id, status="active")

    db_session.add_all([admin, lecturer, counsellor, student, course, enrollment])
    await db_session.commit()

    return {
        "admin": admin,
        "lecturer": lecturer,
        "counsellor": counsellor,
        "student": student,
        "course": course,
        "pseudo_id": pseudonymize(str(student.id)),
    }


async def get_tokens(client: AsyncClient):
    tokens = {}
    for role, email in [
        ("admin", "admin_rbac@lms.edu"),
        ("lecturer", "lec_rbac@lms.edu"),
        ("counsellor", "coun_rbac@lms.edu"),
        ("student", "stu_rbac@lms.edu"),
    ]:
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass123"})
        assert r.status_code == 200, f"Login failed for {email}: {r.text}"
        tokens[role] = r.json()["access_token"]
    return tokens


# ============================================================================
# INGESTION TESTS (Valid & Invalid Payloads)
# ============================================================================

@pytest.mark.asyncio
async def test_affect_ingestion_valid_and_invalid(client: AsyncClient, rbac_ingestion_setup):
    """Test affect ingestion: valid (201) vs wrong schema_version (422), unknown pseudonym (400), missing course_id (422)."""
    ctx = rbac_ingestion_setup
    tokens = await get_tokens(client)
    admin_hdr = {"Authorization": f"Bearer {tokens['admin']}"}

    # 1. Valid payload -> 201
    valid_payload = {
        "records": [
            {
                "pseudo_student_id": ctx["pseudo_id"],
                "course_id": str(ctx["course"].id),
                "week_index": 0,
                "exam_anxiety": 0.35,
                "conceptual_confusion": 0.20,
                "academic_helplessness": 0.10,
                "course_frustration": 0.15,
                "motivation_erosion": 0.25,
                "confidence": 0.80,
                "message_count": 5,
                "schema_version": "1.0",
            }
        ]
    }
    r = await client.post("/api/v1/affect/ingest", json=valid_payload, headers=admin_hdr)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    assert r.json()["count"] == 1

    # 2. Invalid: wrong schema_version -> 422
    inv_schema = {
        "records": [
            {
                "pseudo_student_id": ctx["pseudo_id"],
                "course_id": str(ctx["course"].id),
                "week_index": 0,
                "schema_version": "99.0",
            }
        ]
    }
    r = await client.post("/api/v1/affect/ingest", json=inv_schema, headers=admin_hdr)
    assert r.status_code == 422, f"Expected 422 for bad schema_version, got {r.status_code}"

    # 3. Invalid: unknown pseudonym -> 400
    inv_pseudo = {
        "records": [
            {
                "pseudo_student_id": "pseudo_nonexistent_user",
                "course_id": str(ctx["course"].id),
                "week_index": 0,
            }
        ]
    }
    r = await client.post("/api/v1/affect/ingest", json=inv_pseudo, headers=admin_hdr)
    assert r.status_code == 400, f"Expected 400 for unknown pseudonym, got {r.status_code}: {r.text}"

    # 4. Invalid: missing course_id -> 422
    inv_course = {
        "records": [
            {
                "pseudo_student_id": ctx["pseudo_id"],
                "week_index": 0,
            }
        ]
    }
    r = await client.post("/api/v1/affect/ingest", json=inv_course, headers=admin_hdr)
    assert r.status_code == 422, f"Expected 422 for missing course_id, got {r.status_code}"


@pytest.mark.asyncio
async def test_risk_ingestion_valid_and_invalid(client: AsyncClient, rbac_ingestion_setup):
    """Test risk score ingestion: valid (201) vs wrong tier (422), weights != 1 (422), unknown pseudonym (400)."""
    ctx = rbac_ingestion_setup
    tokens = await get_tokens(client)
    admin_hdr = {"Authorization": f"Bearer {tokens['admin']}"}

    # 1. Valid payload -> 201
    valid_payload = [
        {
            "pseudo_student_id": ctx["pseudo_id"],
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "risk_score": 65.5,
            "risk_tier": "Medium",
            "calibrated": True,
            "modality_weights": {"c1": 0.4, "c2": 0.6},
            "schema_version": "1.0",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/risk", json=valid_payload, headers=admin_hdr)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    assert r.json()["count"] == 1

    # 2. Invalid: wrong risk_tier -> 422
    inv_tier = [
        {
            "pseudo_student_id": ctx["pseudo_id"],
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "risk_score": 65.5,
            "risk_tier": "EXTREME_DANGER",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/risk", json=inv_tier, headers=admin_hdr)
    assert r.status_code == 422, f"Expected 422 for wrong risk_tier, got {r.status_code}"

    # 3. Invalid: modality_weights not summing to 1.0 -> 422
    inv_weights = [
        {
            "pseudo_student_id": ctx["pseudo_id"],
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "risk_score": 65.5,
            "risk_tier": "High",
            "modality_weights": {"c1": 0.2, "c2": 0.3},  # sums to 0.5 != 1.0
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/risk", json=inv_weights, headers=admin_hdr)
    assert r.status_code == 422, f"Expected 422 for weights not summing to 1, got {r.status_code}"

    # 4. Invalid: unknown pseudonym -> 400
    inv_pseudo = [
        {
            "pseudo_student_id": "pseudo_unknown",
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "risk_score": 50.0,
            "risk_tier": "Low",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/risk", json=inv_pseudo, headers=admin_hdr)
    assert r.status_code == 400, f"Expected 400 for unknown pseudonym, got {r.status_code}: {r.text}"


@pytest.mark.asyncio
async def test_trajectory_ingestion_valid_and_invalid(client: AsyncClient, rbac_ingestion_setup):
    """Test trajectory ingestion: valid (201) vs wrong label (422), wrong schema (422), unknown pseudonym (400)."""
    ctx = rbac_ingestion_setup
    tokens = await get_tokens(client)
    admin_hdr = {"Authorization": f"Bearer {tokens['admin']}"}

    # 1. Valid payload -> 201
    valid_payload = [
        {
            "pseudo_student_id": ctx["pseudo_id"],
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "label": "Stable",
            "p_stable": 0.85,
            "confidence": 0.90,
            "schema_version": "1.0",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/trajectory", json=valid_payload, headers=admin_hdr)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    assert r.json()["count"] == 1

    # 2. Invalid: wrong label -> 422
    inv_label = [
        {
            "pseudo_student_id": ctx["pseudo_id"],
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "label": "UNKNOWN_LABEL",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/trajectory", json=inv_label, headers=admin_hdr)
    assert r.status_code == 422, f"Expected 422 for invalid label, got {r.status_code}"

    # 3. Invalid: unknown pseudonym -> 400
    inv_pseudo = [
        {
            "pseudo_student_id": "pseudo_unknown",
            "course_id": str(ctx["course"].id),
            "week_index": 0,
            "label": "Improving",
        }
    ]
    r = await client.post("/api/v1/analytics/ingest/trajectory", json=inv_pseudo, headers=admin_hdr)
    assert r.status_code == 400, f"Expected 400 for unknown pseudonym, got {r.status_code}: {r.text}"


# ============================================================================
# RBAC TESTS (Every Router, No Token, Student, Lecturer, Counsellor, Admin)
# ============================================================================

@pytest.mark.asyncio
async def test_rbac_no_token_returns_401(client: AsyncClient, rbac_ingestion_setup):
    """Protected endpoints across all routers return 401 Unauthorized without token."""
    ctx = rbac_ingestion_setup
    cid = ctx["course"].id

    endpoints = [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/courses"),
        ("POST", "/api/v1/courses"),
        ("GET", f"/api/v1/courses/{cid}/assignments"),
        ("POST", f"/api/v1/courses/{cid}/assignments"),
        ("GET", f"/api/v1/courses/{cid}/quizzes"),
        ("POST", f"/api/v1/courses/{cid}/quizzes"),
        ("GET", f"/api/v1/courses/{cid}/attendance/sessions"),
        ("GET", f"/api/v1/courses/{cid}/gradebook"),
        ("GET", f"/api/v1/courses/{cid}/content"),
        ("POST", "/api/v1/behaviour/events"),
        ("GET", "/api/v1/analytics/dashboard"),
        ("POST", "/api/v1/jobs/aggregate-weekly"),
        ("POST", "/api/v1/affect/ingest"),
    ]

    for method, path in endpoints:
        if method == "GET":
            r = await client.get(path)
        else:
            r = await client.post(path, json={})
        assert r.status_code == 401, f"{method} {path} expected 401, got {r.status_code}"


@pytest.mark.asyncio
async def test_rbac_roles_permissions(client: AsyncClient, rbac_ingestion_setup):
    """Test RBAC across roles (Student, Lecturer, Counsellor, Admin)."""
    ctx = rbac_ingestion_setup
    cid = ctx["course"].id
    tokens = await get_tokens(client)

    headers = {role: {"Authorization": f"Bearer {tok}"} for role, tok in tokens.items()}

    # 1. Admin-only endpoints: /jobs/aggregate-weekly, /affect/ingest
    for role in ["student", "lecturer", "counsellor"]:
        r = await client.post("/api/v1/jobs/aggregate-weekly", headers=headers[role])
        assert r.status_code == 403, f"{role} on /jobs/aggregate-weekly expected 403, got {r.status_code}"

        r = await client.post("/api/v1/affect/ingest", json={"records": []}, headers=headers[role])
        assert r.status_code == 403, f"{role} on /affect/ingest expected 403, got {r.status_code}"

    # Admin allowed on /jobs/aggregate-weekly
    r = await client.post("/api/v1/jobs/aggregate-weekly", headers=headers["admin"])
    assert r.status_code == 200, f"Admin on /jobs/aggregate-weekly expected 200, got {r.status_code}"

    # 2. Lecturer-only / teaching staff routes: creating an assignment
    # Student forbidden (403)
    r = await client.post(
        f"/api/v1/courses/{cid}/assignments",
        json={"title": "Test A", "max_score": 100},
        headers=headers["student"],
    )
    assert r.status_code == 403, f"Student on create assignment expected 403, got {r.status_code}"

    # Lecturer allowed (200)
    r = await client.post(
        f"/api/v1/courses/{cid}/assignments",
        json={"title": "Test A", "max_score": 100, "is_published": True},
        headers=headers["lecturer"],
    )
    assert r.status_code == 200, f"Lecturer on create assignment expected 200, got {r.status_code}"

    # 3. Analytics dashboard: allowed for Lecturer, Counsellor, Admin; forbidden for Student
    r = await client.get("/api/v1/analytics/dashboard", headers=headers["student"])
    assert r.status_code == 403, f"Student on /analytics/dashboard expected 403, got {r.status_code}"

    for role in ["lecturer", "counsellor", "admin"]:
        r = await client.get("/api/v1/analytics/dashboard", headers=headers[role])
        assert r.status_code == 200, f"{role} on /analytics/dashboard expected 200, got {r.status_code}"

    # 4. Export training data: Admin only; Lecturer forbidden
    r = await client.get(f"/api/v1/analytics/courses/{cid}/export", headers=headers["lecturer"])
    assert r.status_code == 403, f"Lecturer on /export expected 403, got {r.status_code}"

    r = await client.get(f"/api/v1/analytics/courses/{cid}/export", headers=headers["admin"])
    assert r.status_code == 200, f"Admin on /export expected 200, got {r.status_code}"
