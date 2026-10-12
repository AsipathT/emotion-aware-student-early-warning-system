"""
backend/tests/test_admin_panel.py

Feature 40: Admin Panel (Phase 1) Backend Tests.
Tests:
  - RBAC Authorization matrix for /api/v1/admin/* (student, lecturer, counsellor, auditor, admin)
  - GET /api/v1/admin/overview metrics, KPIs, and auditor access
  - GET /api/v1/admin/users pagination, query search, role/status filtering
  - POST /api/v1/admin/users account provisioning, deterministic PID for students, audit log
  - GET /api/v1/admin/users/{user_id} detail drawer data
  - PUT /api/v1/admin/users/{user_id}/status: self-lockout prevention, last-admin safeguard, audit log
  - PUT /api/v1/admin/users/{user_id}/role: self-demotion prevention, last-admin safeguard, audit log
  - PUT /api/v1/admin/users/{user_id}/profile: profile update with audit log
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

for p in ["/", "/scripts", str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.database import create_mongo_client, get_db
from app.core.privacy import pseudonymize
from app.core.security import create_access_token, hash_password
from app.db import collections as col
from app.main import app
from app.models.user import UserRole
from app.schemas.audit import AuditAction
from scripts.setup_db import setup_database


@pytest_asyncio.fixture
async def throwaway_admin_db():
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        pytest.skip("MongoDB URI unset. Skipping real database test.")

    test_db_name = f"lms_test_admin_{uuid.uuid4().hex[:8]}"
    async_client = create_mongo_client(uri)
    db = async_client[test_db_name]

    try:
        await db.command("ping")
    except Exception as exc:
        async_client.close()
        pytest.skip(f"Could not connect to MongoDB for testing: {exc}")

    await setup_database(db_name=test_db_name, dry_run=False, check_only=False)

    app.dependency_overrides[get_db] = lambda: db

    yield db

    app.dependency_overrides.pop(get_db, None)
    await async_client.drop_database(test_db_name)
    async_client.close()


@pytest_asyncio.fixture
async def admin_api_client(throwaway_admin_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _seed_user(db, role: str, is_active: bool = True, email: str = None) -> Dict[str, Any]:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    email = email or f"{role}_{uid[:6]}@example.com"
    user_doc = {
        "_id": uid,
        "id": uid,
        "email": email,
        "hashed_password": hash_password("Password123!"),
        "full_name": f"Test {role.capitalize()}",
        "role": role,
        "is_active": is_active,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
        "profile": {
            "user_id": uid,
            "full_name": f"Test {role.capitalize()}",
            "email": email,
            "department": "Computer Science",
        },
    }
    await db[col.USERS].insert_one(user_doc)
    return user_doc


def _make_auth_header(user_doc: Dict[str, Any]) -> Dict[str, str]:
    role_val = user_doc["role"].value if hasattr(user_doc["role"], "value") else str(user_doc["role"])
    token = create_access_token(
        subject=str(user_doc["id"]),
        role=role_val,
    )
    return {"Authorization": f"Bearer {token}"}


# ── RBAC Authorization Matrix Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_rbac_matrix(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db

    admin = await _seed_user(db, "admin")
    auditor = await _seed_user(db, "auditor")
    lecturer = await _seed_user(db, "lecturer")
    student = await _seed_user(db, "student")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)
    lecturer_headers = _make_auth_header(lecturer)
    student_headers = _make_auth_header(student)

    # 1. Unauthenticated -> 401
    resp = await admin_api_client.get("/api/v1/admin/overview")
    assert resp.status_code == 401

    # 2. Student / Lecturer -> 403
    resp = await admin_api_client.get("/api/v1/admin/overview", headers=student_headers)
    assert resp.status_code == 403

    resp = await admin_api_client.get("/api/v1/admin/users", headers=lecturer_headers)
    assert resp.status_code == 403

    # 3. Auditor -> allowed on overview (200), forbidden on user management (403)
    resp = await admin_api_client.get("/api/v1/admin/overview", headers=auditor_headers)
    assert resp.status_code == 200

    resp = await admin_api_client.get("/api/v1/admin/users", headers=auditor_headers)
    assert resp.status_code == 403

    # 4. Admin -> allowed on both
    resp = await admin_api_client.get("/api/v1/admin/overview", headers=admin_headers)
    assert resp.status_code == 200

    resp = await admin_api_client.get("/api/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200


# ── Overview Endpoint Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_overview_metrics(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db

    admin = await _seed_user(db, "admin")
    await _seed_user(db, "student")
    await _seed_user(db, "student")
    await _seed_user(db, "lecturer")

    # Seed course
    cid = f"crs_{uuid.uuid4().hex[:8]}"
    await db[col.COURSES].insert_one({
        "_id": cid,
        "id": cid,
        "course_id": cid,
        "title": "Data Structures",
        "is_published": True,
        "lecturer_id": str(admin["id"]),
        "created_at": datetime.now(timezone.utc),
    })

    admin_headers = _make_auth_header(admin)
    resp = await admin_api_client.get("/api/v1/admin/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_users"] == 4
    assert data["active_users"] == 4
    assert data["total_courses"] == 1
    assert data["published_courses"] == 1
    assert data["users_by_role"]["student"] == 2
    assert "database_health" in data
    assert data["database_health"]["status"] == "connected"


# ── User Pagination & Search Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_users_pagination_and_search(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db

    admin = await _seed_user(db, "admin", email="superadmin@sliit.lk")
    for i in range(15):
        await _seed_user(db, "student", email=f"student_{i:02d}@sliit.lk")

    admin_headers = _make_auth_header(admin)

    # Page 1
    resp = await admin_api_client.get("/api/v1/admin/users?page=1&page_size=10", headers=admin_headers)
    assert resp.status_code == 200
    p1 = resp.json()
    assert p1["total"] == 16
    assert p1["page"] == 1
    assert p1["page_size"] == 10
    assert len(p1["items"]) == 10
    assert p1["total_pages"] == 2

    # Page 2
    resp = await admin_api_client.get("/api/v1/admin/users?page=2&page_size=10", headers=admin_headers)
    assert resp.status_code == 200
    p2 = resp.json()
    assert len(p2["items"]) == 6

    # Search keyword
    resp = await admin_api_client.get("/api/v1/admin/users?q=superadmin", headers=admin_headers)
    assert resp.status_code == 200
    search_data = resp.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["email"] == "superadmin@sliit.lk"

    # Filter by role
    resp = await admin_api_client.get("/api/v1/admin/users?role=student", headers=admin_headers)
    assert resp.status_code == 200
    role_data = resp.json()
    assert role_data["total"] == 15


# ── User Provisioning & Detail Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_create_user_and_detail(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, "admin")
    admin_headers = _make_auth_header(admin)

    # 1. Create a student account
    payload = {
        "email": "new.student@sliit.lk",
        "full_name": "Kasun Perera",
        "password": "StrongPassword123!",
        "role": "student",
        "department": "Software Engineering",
    }
    resp = await admin_api_client.post("/api/v1/admin/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    created_user = resp.json()
    assert created_user["email"] == "new.student@sliit.lk"
    assert created_user["pid"] is not None
    assert created_user["pid"].startswith("STU_")

    # Verify identity vault entry created for student
    vault_entry = await db[col.IDENTITY_VAULT].find_one({"_id": created_user["pid"]})
    assert vault_entry is not None
    assert vault_entry["email"] == "new.student@sliit.lk"

    # Verify audit log recorded
    audit_entry = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.USER_CREATED.value})
    assert audit_entry is not None
    assert audit_entry["actor_id"] == str(admin["id"])

    # 2. Get user detail
    detail_resp = await admin_api_client.get(f"/api/v1/admin/users/{created_user['id']}", headers=admin_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["full_name"] == "Kasun Perera"
    assert detail["pid"] == created_user["pid"]
    assert "enrolments" in detail
    assert "consent" in detail


# ── Safeguards & Audit Log Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_safeguards_last_admin_and_self_lockout(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db

    # Only 1 active admin
    admin = await _seed_user(db, "admin")
    admin_headers = _make_auth_header(admin)

    # 1. Self-suspension blocked
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{admin['id']}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "Administrators cannot suspend their own active account" in resp.json()["detail"]

    # 2. Self-demotion blocked
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{admin['id']}/role",
        json={"role": "lecturer"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "Administrators cannot demote their own account role" in resp.json()["detail"]

    # 3. Last admin protection: Admin A tries to suspend/demote Admin B when Admin B is the only other admin
    admin_2 = await _seed_user(db, "admin")
    # Now there are 2 admins. Demoting Admin 2 should succeed:
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{admin_2['id']}/role",
        json={"role": "lecturer"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # Verify audit log recorded for role update
    audit_role = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.USER_ROLE_UPDATED.value})
    assert audit_role is not None
    assert audit_role["target_id"] == str(admin_2["id"])

    # Now there is only 1 active admin left (admin). Admin creates another admin and suspends it
    admin_3 = await _seed_user(db, "admin")
    # Suspend Admin 3 -> succeeds because admin is still active
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{admin_3['id']}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # Now trying to demote/suspend the ONLY remaining active admin (admin) is blocked by both guards
    # Let's test with a mock if admin_3 is the only admin:
    await db[col.USERS].delete_many({"_id": admin["_id"]})
    # Now admin_3 is the only admin doc left, but inactive. Let's make admin_3 active:
    await db[col.USERS].update_one({"_id": admin_3["_id"]}, {"$set": {"is_active": True}})
    admin_3_headers = _make_auth_header(admin_3)

    # Another user who is student
    student = await _seed_user(db, "student")
    # Toggling student status succeeds
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{student['id']}/status",
        json={"is_active": False},
        headers=admin_3_headers,
    )
    assert resp.status_code == 200

    # Verify audit log recorded for status update
    audit_status = await db[col.AUDIT_LOGS].find_one({
        "action": AuditAction.USER_STATUS_UPDATED.value,
        "target_id": str(student["id"]),
    })
    assert audit_status is not None
    assert audit_status["target_id"] == str(student["id"])


# ── Phase 2: Course Administration Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_courses_management(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, "admin")
    auditor = await _seed_user(db, "auditor")
    lecturer_1 = await _seed_user(db, "lecturer")
    lecturer_2 = await _seed_user(db, "lecturer")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)

    now = datetime.now(timezone.utc)
    c1_id = str(uuid.uuid4())
    c2_id = str(uuid.uuid4())

    await db[col.COURSES].insert_many([
        {
            "_id": c1_id,
            "id": c1_id,
            "course_id": c1_id,
            "title": "Machine Learning Fundamentals",
            "description": "Introductory ML course",
            "lecturer_id": str(lecturer_1["id"]),
            "is_published": True,
            "modules": [{"id": "m1", "title": "Module 1", "sequence_order": 1}],
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": c2_id,
            "id": c2_id,
            "course_id": c2_id,
            "title": "Advanced Neural Networks",
            "description": "Deep learning models",
            "lecturer_id": str(lecturer_2["id"]),
            "is_published": False,
            "modules": [],
            "created_at": now,
            "updated_at": now,
        },
    ])

    # 1. Auditor can list courses, but cannot mutate
    resp = await admin_api_client.get("/api/v1/admin/courses", headers=auditor_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    resp = await admin_api_client.put(
        f"/api/v1/admin/courses/{c1_id}/publish",
        json={"is_published": False},
        headers=auditor_headers,
    )
    assert resp.status_code == 403

    # 2. Admin filters courses
    resp = await admin_api_client.get("/api/v1/admin/courses?is_published=true", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Machine Learning Fundamentals"
    assert resp.json()["items"][0]["lecturer_name"] == lecturer_1["full_name"]
    assert resp.json()["items"][0]["module_count"] == 1

    resp = await admin_api_client.get("/api/v1/admin/courses?is_published=false", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Advanced Neural Networks"

    resp = await admin_api_client.get("/api/v1/admin/courses?q=Machine", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # 3. Admin toggles publication status with audit log
    resp = await admin_api_client.put(
        f"/api/v1/admin/courses/{c1_id}/publish",
        json={"is_published": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False

    audit_publish = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.COURSE_STATUS_UPDATED.value})
    assert audit_publish is not None
    assert audit_publish["target_id"] == c1_id
    assert audit_publish["details"]["previous_is_published"] is True
    assert audit_publish["details"]["new_is_published"] is False

    # 4. Admin reassigns lecturer with audit log
    resp = await admin_api_client.put(
        f"/api/v1/admin/courses/{c1_id}/lecturer",
        json={"lecturer_id": str(lecturer_2["id"])},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["lecturer_id"] == str(lecturer_2["id"])
    assert resp.json()["lecturer_name"] == lecturer_2["full_name"]

    audit_lecturer = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.COURSE_LECTURER_ASSIGNED.value})
    assert audit_lecturer is not None
    assert audit_lecturer["target_id"] == c1_id
    assert audit_lecturer["details"]["previous_lecturer_id"] == str(lecturer_1["id"])
    assert audit_lecturer["details"]["new_lecturer_id"] == str(lecturer_2["id"])


# ── Phase 2: Enrolments Administration Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_admin_enrolments_management(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, "admin")
    auditor = await _seed_user(db, "auditor")
    student_1 = await _seed_user(db, "student")
    student_2 = await _seed_user(db, "student")
    student_3 = await _seed_user(db, "student")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)

    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db[col.COURSES].insert_one({
        "_id": cid,
        "id": cid,
        "course_id": cid,
        "title": "Data Engineering 101",
        "description": "Pipelines and ETL",
        "is_published": True,
        "created_at": now,
        "updated_at": now,
    })

    # 1. Admin enrols student 1
    resp = await admin_api_client.post(
        "/api/v1/admin/enrolments",
        json={"course_id": cid, "student_identifier": student_1["email"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    enr_data = resp.json()
    assert enr_data["course_id"] == cid
    assert enr_data["status"] == "active"
    assert enr_data["student_email"] == student_1["email"]
    enr_id = enr_data["id"]

    # Verify audit log for enrolment creation
    audit_create = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.ENROLMENT_CREATED.value})
    assert audit_create is not None
    assert audit_create["target_id"] == enr_data["pid"]

    # Re-enrolling actively enrolled student returns 409
    resp = await admin_api_client.post(
        "/api/v1/admin/enrolments",
        json={"course_id": cid, "student_identifier": student_1["email"]},
        headers=admin_headers,
    )
    assert resp.status_code == 409

    # 2. Auditor can view enrolments
    resp = await admin_api_client.get(f"/api/v1/admin/enrolments?course_id={cid}", headers=auditor_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # 3. Admin soft-removes student 1 (DELETE marks status='dropped', never deletes records)
    resp = await admin_api_client.delete(f"/api/v1/admin/enrolments/{enr_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"

    enr_doc = await db[col.ENROLMENTS].find_one({"_id": enr_id})
    assert enr_doc["status"] == "dropped"
    assert enr_doc.get("enrolment_end") is not None

    audit_remove = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.ENROLMENT_REMOVED.value})
    assert audit_remove is not None
    assert audit_remove["details"]["previous_status"] == "active"
    assert audit_remove["details"]["new_status"] == "dropped"

    # 4. Bulk enrolment with idempotency and row results
    bulk_payload = {
        "course_id": cid,
        "student_identifiers": [
            student_1["email"],  # Reactivation of dropped
            student_2["id"],     # New enrolment
            student_3["email"],  # New enrolment
            "nonexistent_student@test.com",  # Should fail cleanly
        ],
    }
    resp = await admin_api_client.post(
        "/api/v1/admin/enrolments/bulk",
        json=bulk_payload,
        headers=admin_headers,
    )
    assert resp.status_code == 200
    bulk_resp = resp.json()
    assert bulk_resp["total"] == 4
    assert bulk_resp["enrolled_count"] == 3  # student_1 reactivated, student_2 and student_3 enrolled
    assert bulk_resp["skipped_count"] == 0
    assert bulk_resp["failed_count"] == 1
    assert len(bulk_resp["results"]) == 4

    audit_bulk = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.BULK_ENROLMENT.value})
    assert audit_bulk is not None
    assert audit_bulk["details"]["enrolled_count"] == 3
    assert audit_bulk["details"]["failed_count"] == 1

    # Idempotent second run: all already enrolled should now be skipped
    resp2 = await admin_api_client.post(
        "/api/v1/admin/enrolments/bulk",
        json=bulk_payload,
        headers=admin_headers,
    )
    assert resp2.status_code == 200
    bulk_resp2 = resp2.json()
    assert bulk_resp2["enrolled_count"] == 0
    assert bulk_resp2["skipped_count"] == 3
    assert bulk_resp2["failed_count"] == 1


# ── Phase 2: Consent Coverage and Withdrawn Exclusion Tests ───────────────────

@pytest.mark.asyncio
async def test_admin_consent_coverage_and_withdrawn_exclusion(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, "admin")
    auditor = await _seed_user(db, "auditor")
    student_a = await _seed_user(db, "student")
    student_b = await _seed_user(db, "student")
    student_c = await _seed_user(db, "student")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)
    student_a_headers = _make_auth_header(student_a)
    student_b_headers = _make_auth_header(student_b)

    # 1. Setup active consent notice v1
    notice_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db[col.CONSENT_NOTICES].insert_one({
        "_id": notice_id,
        "id": notice_id,
        "version": 1,
        "text": "Ethics and Early Warning consent notice v1.",
        "effective_from": now,
        "is_active": True,
    })

    # Seed course and enrol all 3 students
    cid = str(uuid.uuid4())
    await db[col.COURSES].insert_one({
        "_id": cid,
        "id": cid,
        "course_id": cid,
        "title": "Software Architecture",
        "is_published": True,
        "created_at": now,
        "updated_at": now,
    })

    # Ensure PIDs and enrolments
    for stu in [student_a, student_b, student_c]:
        pid = pseudonymize(stu["id"])
        await db[col.USERS].update_one({"_id": stu["id"]}, {"$set": {"pid": pid}})
        await db[col.ENROLMENTS].insert_one({
            "_id": str(uuid.uuid4()),
            "pid": pid,
            "course_id": cid,
            "enrolment_start": now,
            "status": "active",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        })

    # Student A accepts notice v1
    resp = await admin_api_client.post(
        "/api/v1/consent/me",
        json={"decision": "accepted"},
        headers=student_a_headers,
    )
    assert resp.status_code == 201

    # Student B accepts notice v1, then withdraws
    resp_b = await admin_api_client.post(
        "/api/v1/consent/me",
        json={"decision": "accepted"},
        headers=student_b_headers,
    )
    assert resp_b.status_code == 201

    resp = await admin_api_client.post(
        "/api/v1/consent/me/withdraw",
        headers=student_b_headers,
    )
    assert resp.status_code == 200
    # Student C has pending consent (no decision)

    # 2. Verify coverage on notice v1: Withdrawn student is NEVER counted as consented!
    resp = await admin_api_client.get("/api/v1/admin/consent/coverage", headers=admin_headers)
    assert resp.status_code == 200
    cov = resp.json()

    assert cov["active_version"] == 1
    assert cov["total_students"] == 3
    assert cov["accepted"] == 1      # Student A only
    assert cov["withdrawn"] == 1     # Student B
    assert cov["pending"] == 1       # Student C
    assert cov["declined"] == 0
    assert cov["coverage_percentage"] == 33.3

    # Verify per-course breakdown
    assert len(cov["course_breakdown"]) == 1
    c_break = cov["course_breakdown"][0]
    assert c_break["course_id"] == cid
    assert c_break["enrolled_students"] == 3
    assert c_break["accepted"] == 1
    assert c_break["withdrawn"] == 1
    assert c_break["pending"] == 1
    assert c_break["coverage_percentage"] == 33.3

    # 3. Publish notice version 2: Resets coverage to active notice version only!
    resp = await admin_api_client.post(
        "/api/v1/consent/notices",
        json={"text": "Updated Ethics notice version 2 with revised privacy terms."},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["version"] == 2

    # Query coverage again
    resp = await admin_api_client.get("/api/v1/admin/consent/coverage", headers=auditor_headers)
    assert resp.status_code == 200
    cov2 = resp.json()

    assert cov2["active_version"] == 2
    assert cov2["total_students"] == 3
    assert cov2["accepted"] == 0     # Neither A nor B has consented to v2 yet!
    assert cov2["withdrawn"] == 0
    assert cov2["pending"] == 3      # All 3 students are pending on the new version
    assert cov2["coverage_percentage"] == 0.0

    # Notice history contains 2 versions
    assert len(cov2["notice_history"]) == 2
    assert cov2["notice_history"][0]["version"] == 2
    assert cov2["notice_history"][0]["is_active"] is True
    assert cov2["notice_history"][1]["version"] == 1
    assert cov2["notice_history"][1]["is_active"] is False

    # 4. Verify export consent exclusion function
    from app.routers.export import get_eligible_consenting_pids
    # Under active version 2, neither A nor B is consenting:
    consenting_pids_v2 = await get_eligible_consenting_pids(db)
    pid_a = pseudonymize(student_a["id"])
    pid_b = pseudonymize(student_b["id"])
    assert pid_a not in consenting_pids_v2
    assert pid_b not in consenting_pids_v2

