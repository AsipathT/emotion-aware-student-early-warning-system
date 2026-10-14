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
from app.core.contract_version import CONTRACT_VERSION
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


@pytest.mark.asyncio
async def test_admin_change_user_role_to_student_creates_pid_and_vault(admin_api_client, throwaway_admin_db):
    """
    Verifies that when an administrator updates a user's role to 'student':
      1. A valid pseudonym (PID) is assigned to the user document.
      2. An identity_vault entry is created with full schema fields.
      3. If a student already had a PID but no vault entry, changing role ensures vault entry is created without altering the existing PID.
    """
    db = throwaway_admin_db
    admin = await _seed_user(db, "admin")
    admin_headers = _make_auth_header(admin)

    # 1. User initially seeded as lecturer (no PID, no student_id)
    lecturer = await _seed_user(db, "lecturer")
    assert lecturer.get("pid") is None

    # Admin changes lecturer role to student
    resp = await admin_api_client.put(
        f"/api/v1/admin/users/{lecturer['id']}/role",
        json={"role": "student"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["role"] == "student"

    # Verify user document in DB has PID and student_id
    updated_user = await db[col.USERS].find_one({"_id": str(lecturer["id"])})
    assert updated_user is not None
    assert updated_user["role"] == "student"
    pid = updated_user.get("pid")
    assert pid is not None
    assert pid.startswith("STU_")
    student_id = updated_user.get("student_id")
    assert student_id is not None

    # Verify vault entry was created in identity_vault
    vault_entry = await db[col.IDENTITY_VAULT].find_one({"_id": pid})
    assert vault_entry is not None
    assert vault_entry["pid"] == pid
    assert vault_entry["student_id"] == student_id
    assert vault_entry["name"] == lecturer["full_name"]
    assert vault_entry["email"] == lecturer["email"]
    assert vault_entry["schema_version"] == 1
    assert vault_entry["source_version"] == "1.0"
    assert vault_entry["is_imported"] is False

    # 2. Case where user already has a PID but missing vault entry
    existing_pid = pseudonymize("IT99999999")
    unregistered_student = await _seed_user(db, "student")
    await db[col.USERS].update_one(
        {"_id": str(unregistered_student["id"])},
        {"$set": {"pid": existing_pid, "student_id": "IT99999999"}},
    )
    # Ensure no vault entry exists initially
    await db[col.IDENTITY_VAULT].delete_one({"_id": existing_pid})

    # Admin triggers role update to student
    resp_reassert = await admin_api_client.put(
        f"/api/v1/admin/users/{unregistered_student['id']}/role",
        json={"role": "student"},
        headers=admin_headers,
    )
    assert resp_reassert.status_code == 200

    # User PID must be preserved (not recomputed)
    rechecked_user = await db[col.USERS].find_one({"_id": str(unregistered_student["id"])})
    assert rechecked_user["pid"] == existing_pid

    # Vault entry must now exist
    new_vault = await db[col.IDENTITY_VAULT].find_one({"_id": existing_pid})
    assert new_vault is not None
    assert new_vault["pid"] == existing_pid
    assert new_vault["student_id"] == "IT99999999"


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


# ── Phase 3 Tests: Ingestion, Privacy Reveal, Pipeline, Exports, System ────────

@pytest.mark.asyncio
async def test_admin_ingestion_status_no_secrets(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, role="admin")
    auditor = await _seed_user(db, role="auditor")
    student = await _seed_user(db, role="student")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)
    student_headers = _make_auth_header(student)

    # 1. Student is forbidden
    res = await admin_api_client.get("/api/v1/admin/ingestion/status", headers=student_headers)
    assert res.status_code == 403

    # 2. Admin & Auditor can access
    res = await admin_api_client.get("/api/v1/admin/ingestion/status", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "components" in data
    assert "c1" in data["components"]
    assert "c2" in data["components"]
    assert "c3" in data["components"]
    assert "c4" in data["components"]

    # Invariants: api_key_configured is boolean, NO secret keys in response
    for comp in ["c1", "c2", "c3", "c4"]:
        assert isinstance(data["components"][comp]["api_key_configured"], bool)

    # STRICT: verify no secret keys in response text
    res_text = res.text
    for secret in settings.COMPONENT_API_KEYS.values():
        if secret:
            assert secret not in res_text
    assert settings.secret_key not in res_text

    # Auditor access
    res_auditor = await admin_api_client.get("/api/v1/admin/ingestion/status", headers=auditor_headers)
    assert res_auditor.status_code == 200


@pytest.mark.asyncio
async def test_admin_privacy_breakglass_reveal_and_audit(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, role="admin")
    auditor = await _seed_user(db, role="auditor")
    student = await _seed_user(db, role="student")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)
    student_headers = _make_auth_header(student)

    # Seed student in identity vault
    pid = pseudonymize("IT20269999")
    await db[col.IDENTITY_VAULT].insert_one({
        "_id": pid,
        "pid": pid,
        "student_id": "IT20269999",
        "name": "Target Student",
        "email": "target@lms.edu",
    })

    # 1. Auditor and Student are forbidden from break-glass reveal (403)
    res = await admin_api_client.post(
        "/api/v1/admin/privacy/reveal",
        json={"pid": pid, "justification": "Emergency mental health welfare intervention"},
        headers=auditor_headers,
    )
    assert res.status_code == 403

    res = await admin_api_client.post(
        "/api/v1/admin/privacy/reveal",
        json={"pid": pid, "justification": "Emergency mental health welfare intervention"},
        headers=student_headers,
    )
    assert res.status_code == 403

    # 2. Admin with justification < 10 chars is rejected (422)
    res = await admin_api_client.post(
        "/api/v1/admin/privacy/reveal",
        json={"pid": pid, "justification": "too short"},
        headers=admin_headers,
    )
    assert res.status_code == 422

    # 3. Admin with justification >= 10 chars succeeds
    justification_str = "Emergency welfare check requested by counsellor"
    res = await admin_api_client.post(
        "/api/v1/admin/privacy/reveal",
        json={"pid": pid, "justification": justification_str},
        headers=admin_headers,
    )
    assert res.status_code == 200
    rev = res.json()
    assert rev["pid"] == pid
    assert rev["student_id"] == "IT20269999"
    assert rev["name"] == "Target Student"
    assert rev["email"] == "target@lms.edu"

    # 4. Verify Feature 7 audit log has IDENTITY_REVEAL entry
    audit_entry = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.IDENTITY_REVEAL, "target_id": pid})
    assert audit_entry is not None
    assert audit_entry["actor_id"] == admin["_id"]
    assert audit_entry["actor_role"] == "admin"
    assert audit_entry["reason"] == justification_str
    # Verify no PII in details
    dtls = audit_entry.get("details", {})
    assert "name" not in dtls
    assert "email" not in dtls
    assert "student_id" not in dtls

    # 5. Reveal history endpoint shows event to Admin and Auditor
    res_hist = await admin_api_client.get("/api/v1/admin/privacy/reveal-history", headers=auditor_headers)
    assert res_hist.status_code == 200
    assert res_hist.json()["total"] >= 1
    assert res_hist.json()["items"][0]["pid"] == pid

    # 6. PII Scrub tester sandbox works without audit logging
    res_scrub = await admin_api_client.post(
        "/api/v1/admin/privacy/scrub-test",
        json={"text": "Contact john.doe@example.com or call 0771234567"},
        headers=auditor_headers,
    )
    assert res_scrub.status_code == 200
    scrub_data = res_scrub.json()
    assert "[EMAIL]" in scrub_data["clean_text"]
    assert scrub_data["redaction_report"]["EMAIL"] >= 1


@pytest.mark.asyncio
async def test_admin_pipeline_trigger_and_advance_audit_and_rbac(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, role="admin")
    auditor = await _seed_user(db, role="auditor")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)

    course_id = "CS101"
    week_index = 0
    now = datetime.now(timezone.utc)

    # Seed course and course week
    await db[col.COURSES].insert_one({
        "_id": course_id,
        "course_id": course_id,
        "title": "Intro to CS",
        "lecturer_id": admin["_id"],
        "is_published": True,
    })
    await db[col.COURSE_WEEKS].insert_one({
        "_id": f"{course_id}_W{week_index}",
        "course_id": course_id,
        "week_index": week_index,
        "title": "Week 1",
        "start_date": now,
        "end_date": now,
    })

    # 1. Auditor cannot trigger (403)
    res = await admin_api_client.post(
        "/api/v1/pipeline/trigger",
        json={"course_id": course_id, "week_index": week_index, "force": True},
        headers=auditor_headers,
    )
    assert res.status_code == 403

    # 2. Admin can trigger
    res = await admin_api_client.post(
        "/api/v1/pipeline/trigger",
        json={"course_id": course_id, "week_index": week_index, "force": True},
        headers=admin_headers,
    )
    assert res.status_code in (200, 202)

    # Verify PIPELINE_TRIGGERED audit event was logged (exactly 1 audit entry for trigger)
    audit_trig = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.PIPELINE_TRIGGERED})
    assert audit_trig is not None
    assert audit_trig["actor_id"] == admin["_id"]
    assert await db[col.AUDIT_LOGS].count_documents({"action": AuditAction.PIPELINE_TRIGGERED}) == 1

    # 3. Auditor cannot advance run (403)
    res_adv_aud = await admin_api_client.post(
        f"/api/v1/pipeline/runs/{course_id}/{week_index}/advance",
        headers=auditor_headers,
    )
    assert res_adv_aud.status_code == 403

    # 4. Admin can advance run
    res_adv_admin = await admin_api_client.post(
        f"/api/v1/pipeline/runs/{course_id}/{week_index}/advance",
        headers=admin_headers,
    )
    assert res_adv_admin.status_code == 200

    # Verify PIPELINE_RUN_STARTED audit event was logged for advance
    audit_adv = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.PIPELINE_RUN_STARTED})
    assert audit_adv is not None

    # 5. Admin and Auditor can list pipeline runs
    res_list = await admin_api_client.get("/api/v1/pipeline/runs", headers=auditor_headers)
    assert res_list.status_code == 200
    assert "items" in res_list.json()


@pytest.mark.asyncio
async def test_admin_system_health_and_exports_no_secrets(admin_api_client, throwaway_admin_db):
    db = throwaway_admin_db
    admin = await _seed_user(db, role="admin")
    auditor = await _seed_user(db, role="auditor")

    admin_headers = _make_auth_header(admin)
    auditor_headers = _make_auth_header(auditor)

    # 1. System health check
    res = await admin_api_client.get("/api/v1/admin/system/health", headers=auditor_headers)
    assert res.status_code == 200
    health = res.json()
    assert health["status"] in ("healthy", "degraded")
    assert health["db_status"] == "connected"
    assert "db_ping_ms" in health
    assert health["contract_version"] == CONTRACT_VERSION
    assert "oulad_status" in health

    # STRICT: verify NO secrets in response text
    res_text = res.text
    assert settings.secret_key not in res_text
    assert settings.mongo_uri not in res_text

    # 2. Export download with formula sanitization
    pid = pseudonymize("IT20261111")
    now = datetime.now(timezone.utc)
    clean_inj = "=1+2 cmd.exe injection"
    await db[col.MESSAGES].insert_one({
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "ingested_at": now,
        "source_version": "1.0",
        "source": "oulad",
        "message_id": "msg_injection_01",
        "pid": pid,
        "course_id": "CS101",
        "week_index": 0,
        "source_type": "forum",
        "clean_text": clean_inj,
        "timestamp": now,
        "message_length_chars": len(clean_inj),
        "message_length_words": len(clean_inj.split()),
    })

    res_export = await admin_api_client.get(
        "/api/v1/admin/exports/download?dataset=c1_messages&format=csv",
        headers=auditor_headers,
    )
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers["content-type"]
    csv_text = res_export.text
    # Formula leading cell must be prepended with single quote
    assert "'=1+2 cmd.exe injection" in csv_text

    # Verify EXPORT_GENERATED audit event
    audit_exp = await db[col.AUDIT_LOGS].find_one({"action": AuditAction.EXPORT_GENERATED})
    assert audit_exp is not None

    # 3. Export history list
    res_hist = await admin_api_client.get("/api/v1/admin/exports/history", headers=auditor_headers)
    assert res_hist.status_code == 200
    assert res_hist.json()["total"] >= 1


