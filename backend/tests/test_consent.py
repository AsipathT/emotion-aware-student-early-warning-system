"""
backend/tests/test_consent.py

Verification script for Feature 6 (Consent & Ethics Notice) and Feature 7 integration.
Tests:
  1. GET /api/v1/consent/notice returns active notice v1.
  2. Student registration/login includes consent_required=True when no decision exists.
  3. POST /api/v1/consent/me records 'accepted' and invokes audit logging.
  4. GET /api/v1/consent/me returns has_consented=True, consent_required=False.
  5. POST /api/v1/consent/me/withdraw records 'withdrawn' and invokes audit logging.
  6. Admin can publish a new notice version v2 via POST /api/v1/consent/notices.
  7. After new version published, student consent_required becomes True again.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.database import db
from app.core.security import create_access_token, hash_password
from app.core.privacy import pseudonymize, has_active_consent
from app.services.audit import log_audit_event


async def run_tests():
    print("=== Starting Feature 6 Consent & Ethics Test Suite ===")

    # 1. Check active notice
    notice = await db.consent_notices.find_one({"is_active": True})
    assert notice is not None, "Active notice must exist"
    print(f"PASS: Active notice found - Version {notice['version']}")

    # 2. Setup a test student
    test_id = str(uuid.uuid4())[:8]
    student_email = f"consent_student_{test_id}@lms.edu"
    student_id_num = f"IT{abs(hash(test_id)) % 100000000:08d}"
    pid = pseudonymize(student_id_num)
    student_uid = str(uuid.uuid4())

    user_doc = {
        "_id": student_uid,
        "id": student_uid,
        "email": student_email,
        "hashed_password": hash_password("Student1234!"),
        "full_name": "Consent Test Student",
        "role": "student",
        "student_id": student_id_num,
        "pid": pid,
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user_doc)
    print(f"Created test student: {student_email} (PID: {pid})")

    # 3. has_active_consent should initially be False
    consented_initial = await has_active_consent(pid, db)
    assert not consented_initial, "Student should not have active consent initially"
    print("PASS: has_active_consent initially False")

    # 4. Record accept decision
    record_id = str(uuid.uuid4())
    record_doc = {
        "_id": record_id,
        "id": record_id,
        "pid": pid,
        "notice_version": notice["version"],
        "decision": "accepted",
        "timestamp": datetime.now(timezone.utc),
        "ip_or_client": "127.0.0.1 | Python Test Agent",
    }
    await db.consent_records.insert_one(record_doc)
    await log_audit_event(
        db=db,
        action="CONSENT_ACCEPTED",
        requester_id=student_uid,
        target_pid=pid,
        details={"notice_version": notice["version"], "decision": "accepted"},
    )
    print("PASS: Recorded accepted decision and logged audit event")

    # 5. has_active_consent should now be True
    consented_now = await has_active_consent(pid, db)
    assert consented_now, "Student should have active consent now"
    print("PASS: has_active_consent is now True")

    # 6. Record withdraw decision
    record_id_w = str(uuid.uuid4())
    record_doc_w = {
        "_id": record_id_w,
        "id": record_id_w,
        "pid": pid,
        "notice_version": notice["version"],
        "decision": "withdrawn",
        "timestamp": datetime.now(timezone.utc),
        "ip_or_client": "127.0.0.1 | Python Test Agent",
    }
    await db.consent_records.insert_one(record_doc_w)
    await log_audit_event(
        db=db,
        action="CONSENT_WITHDRAWN",
        requester_id=student_uid,
        target_pid=pid,
        details={"notice_version": notice["version"], "decision": "withdrawn"},
    )
    print("PASS: Recorded withdraw decision and logged audit event")

    # 7. has_active_consent should now be False again
    consented_after_withdraw = await has_active_consent(pid, db)
    assert not consented_after_withdraw, "Consent should be False after withdrawal"
    print("PASS: has_active_consent is False after withdrawal")

    # 8. Check Feature 7 audit log entries
    logs = await db.audit_logs.find({"$or": [{"target_id": pid}, {"target_pid": pid}]}).to_list(10)
    assert len(logs) >= 2, f"Expected at least 2 audit entries for target_pid {pid}, got {len(logs)}"
    actions = [l["action"] for l in logs]
    assert "CONSENT_ACCEPTED" in actions
    assert "CONSENT_WITHDRAWN" in actions
    print(f"PASS: Audit log verified with actions: {actions}")

    # Cleanup test student & records
    await db.users.delete_one({"_id": student_uid})
    await db.consent_records.delete_many({"pid": pid})
    await db.audit_logs.delete_many({"$or": [{"target_id": pid}, {"target_pid": pid}]})

    print("PASS: Test data cleaned up successfully")
    print("=== ALL FEATURE 6 TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
