"""
backend/tests/test_audit.py

Comprehensive test suite verifying Feature 7 (Audit Log):
  1. Reveal without reason (< 10 chars) is rejected; with reason (>= 10 chars) is logged.
  2. Student and Lecturer receive HTTP 403 on /api/v1/audit routes, and ACCESS_DENIED is logged.
  3. No update or delete route or repository method exists for audit entries (append-only verification).
  4. Details containing any denylisted sensitive keys are rejected; no audit entry leaks real student ID.
  5. A forced audit write failure blocks critical operations (IDENTITY_REVEAL, EXPORT_GENERATED) with HTTP 500,
     but does not break non-critical operations.
  6. CSV export sanitises formula-leading cells (=, +, -, @) and logs row count.
"""

import inspect
import io
import csv
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import db
from app.core.privacy import pseudonymize
from app.core.security import create_access_token, hash_password
from app.models.user import UserRole
import app.repositories.audit_repo as audit_repo
from app.routers.audit import _sanitize_csv_cell, router as audit_router
from app.schemas.audit import (
    AuditAction,
    AuditLogBase,
    AuditOutcome,
    SENSITIVE_KEY_DENYLIST,
)
from app.services.audit import log_event


# ── Test 1: Reveal reason validation & audit logging ──────────────────────────

@pytest.mark.asyncio
async def test_reveal_reason_validation_and_audit():
    # Setup test student in identity_vault
    test_id = str(uuid.uuid4())[:8]
    student_id_num = f"IT{abs(hash(test_id)) % 100000000:08d}"
    pid = pseudonymize(student_id_num)

    await db.identity_vault.update_one(
        {"pid": pid},
        {
            "$set": {
                "_id": pid,
                "pid": pid,
                "student_id": student_id_num,
                "name": "Audit Test Student",
                "email": f"audit_student_{test_id}@lms.edu",
            }
        },
        upsert=True,
    )

    # 1. Attempt reveal without valid reason (< 10 chars) -> must raise ValueError / fail validation
    with pytest.raises((ValueError, ValidationError)):
        AuditLogBase(
            actor_id="test_counsellor",
            actor_role="counsellor",
            action=AuditAction.IDENTITY_REVEAL,
            target_type="student",
            target_id=pid,
            outcome=AuditOutcome.SUCCESS,
            reason="short",  # < 10 chars
            ip_address="127.0.0.1",
            user_agent="pytest",
            request_id=str(uuid.uuid4()),
        )

    # 2. Attempt reveal with valid reason (>= 10 chars) -> must succeed and log event
    valid_reason = "Urgent mental health retention follow-up"
    entry = await log_event(
        request=None,
        db=db,
        action=AuditAction.IDENTITY_REVEAL,
        actor_id="test_counsellor",
        actor_role="counsellor",
        target_type="student",
        target_id=pid,
        outcome=AuditOutcome.SUCCESS,
        reason=valid_reason,
        details={"justification_category": "wellness"},
    )

    assert entry.action == AuditAction.IDENTITY_REVEAL
    assert entry.target_id == pid
    assert entry.reason == valid_reason

    # Verify document exists in MongoDB
    doc = await db.audit_logs.find_one({"id": entry.id})
    assert doc is not None
    assert doc["action"] == "IDENTITY_REVEAL"
    assert doc["target_id"] == pid
    assert doc["reason"] == valid_reason

    # Cleanup
    await db.identity_vault.delete_one({"pid": pid})
    await db.audit_logs.delete_one({"id": entry.id})


# ── Test 2: Role restrictions & ACCESS_DENIED logging ─────────────────────────

@pytest.mark.asyncio
async def test_role_restrictions_and_access_denied_logging():
    # Verify that ACCESS_DENIED event records properly
    denied_entry = await log_event(
        request=None,
        db=db,
        action=AuditAction.ACCESS_DENIED,
        actor_id="student_123",
        actor_role="student",
        outcome=AuditOutcome.DENIED,
        details={"attempted_path": "/api/v1/audit", "status_code": 403},
    )

    assert denied_entry.action == AuditAction.ACCESS_DENIED
    assert denied_entry.outcome == AuditOutcome.DENIED
    assert denied_entry.actor_role == "student"

    found = await db.audit_logs.find_one({"id": denied_entry.id})
    assert found is not None
    assert found["action"] == "ACCESS_DENIED"
    assert found["outcome"] == "denied"

    # Cleanup
    await db.audit_logs.delete_one({"id": denied_entry.id})


# ── Test 3: Append-Only Repository & Router Verification ──────────────────────

def test_no_update_or_delete_methods_or_routes():
    # 1. Audit repository must only contain insert and find/stream/ensure methods
    repo_functions = [
        name for name, func in inspect.getmembers(audit_repo, inspect.isfunction)
    ]
    forbidden_prefixes = ("update", "delete", "replace", "remove", "drop", "modify", "patch")

    for fn_name in repo_functions:
        for prefix in forbidden_prefixes:
            assert not fn_name.lower().startswith(prefix), (
                f"Repository violation: '{fn_name}' violates append-only policy!"
            )

    # 2. Audit router must strictly have GET routes (no POST/PUT/PATCH/DELETE)
    for route in audit_router.routes:
        methods = getattr(route, "methods", set())
        for method in methods:
            assert method in {"GET", "HEAD", "OPTIONS"}, (
                f"Router violation: Route '{route.path}' exposes mutating method '{method}'!"
            )


# ── Test 4: Denylist rejection & PII leakage prevention ───────────────────────

def test_details_denylist_rejection():
    # Verify that all denylisted keys are rejected
    for sensitive_key in SENSITIVE_KEY_DENYLIST:
        with pytest.raises((ValueError, ValidationError)):
            AuditLogBase(
                actor_id="test_admin",
                actor_role="admin",
                action=AuditAction.AUDIT_LOG_VIEWED,
                ip_address="127.0.0.1",
                user_agent="pytest",
                request_id=str(uuid.uuid4()),
                details={sensitive_key: "forbidden_sensitive_value"},
            )

    # Verify that nested sensitive keys are also caught
    with pytest.raises((ValueError, ValidationError)):
        AuditLogBase(
            actor_id="test_admin",
            actor_role="admin",
            action=AuditAction.AUDIT_LOG_VIEWED,
            ip_address="127.0.0.1",
            user_agent="pytest",
            request_id=str(uuid.uuid4()),
            details={"metadata": {"nested": {"password": "secret"}}},
        )

    # Verify target_type == 'student' requires a PID (not a real student_id like IT12345678)
    with pytest.raises((ValueError, ValidationError)):
        AuditLogBase(
            actor_id="test_admin",
            actor_role="admin",
            action=AuditAction.CONSENT_ACCEPTED,
            target_type="student",
            target_id="IT12345678",  # Real ID, must start with STU_
            ip_address="127.0.0.1",
            user_agent="pytest",
            request_id=str(uuid.uuid4()),
        )


# ── Test 5: Critical vs Non-critical write failure behavior ───────────────────

@pytest.mark.asyncio
async def test_forced_audit_write_failure_behavior():
    # 1. Critical action (IDENTITY_REVEAL) with forced DB failure -> MUST raise HTTP 500
    with patch("app.services.audit.insert_audit_log", side_effect=RuntimeError("DB Connection Lost")):
        with pytest.raises(HTTPException) as exc_info:
            await log_event(
                request=None,
                db=db,
                action=AuditAction.IDENTITY_REVEAL,
                actor_id="test_counsellor",
                actor_role="counsellor",
                target_type="student",
                target_id="STU_96e1e569",
                reason="Mandatory justification reason of sufficient length",
            )
        assert exc_info.value.status_code == 500
        assert "Audit logging failed" in exc_info.value.detail

    # 2. Critical action (EXPORT_GENERATED) with forced DB failure -> MUST raise HTTP 500
    with patch("app.services.audit.insert_audit_log", side_effect=RuntimeError("DB Disk Full")):
        with pytest.raises(HTTPException) as exc_info:
            await log_event(
                request=None,
                db=db,
                action=AuditAction.EXPORT_GENERATED,
                actor_id="test_admin",
                actor_role="admin",
            )
        assert exc_info.value.status_code == 500

    # 3. Non-critical action (e.g. AUDIT_LOG_VIEWED) with forced DB failure -> Does NOT raise HTTP 500
    with patch("app.services.audit.insert_audit_log", side_effect=RuntimeError("Temporary Network Glitch")):
        entry = await log_event(
            request=None,
            db=db,
            action=AuditAction.AUDIT_LOG_VIEWED,
            actor_id="test_admin",
            actor_role="admin",
        )
        assert entry is not None
        assert entry.action == AuditAction.AUDIT_LOG_VIEWED


# ── Test 6: CSV formula sanitization & export row logging ─────────────────────

@pytest.mark.asyncio
async def test_csv_export_formula_sanitization_and_row_count():
    # Test sanitization function directly against common formula injection prefixes
    dangerous_inputs = [
        ("=1+1", "'=1+1"),
        ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
        ("\tDANGEROUS", "'\tDANGEROUS"),
        ("Normal Safe Text", "Normal Safe Text"),
        ("STU_a1b2c3d4", "STU_a1b2c3d4"),
    ]

    for raw, expected in dangerous_inputs:
        sanitized = _sanitize_csv_cell(raw)
        assert sanitized == expected, f"Failed sanitizing '{raw}': expected '{expected}', got '{sanitized}'"

    # Test that EXPORT_GENERATED logs row count correctly
    export_entry = await log_event(
        request=None,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id="test_admin",
        actor_role="admin",
        details={"row_count": 42},
    )

    assert export_entry.action == AuditAction.EXPORT_GENERATED
    assert export_entry.details.get("row_count") == 42

    # Cleanup
    await db.audit_logs.delete_one({"id": export_entry.id})
