"""
backend/app/routers/admin.py

Admin Panel endpoints (MongoDB backed - Feature 40).
Provides platform governance, overview KPIs, and user management.
"""

import csv
import io
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.contract_version import CONTRACT_VERSION
from app.core.database import get_db
from app.core.dependencies import get_current_admin, require_roles
from app.core.privacy import is_valid_pid, pseudonymize, scrub_text
from app.core.security import hash_password
from app.db import collections as col
from app.models.user import User, UserRole
from app.routers.audit import _sanitize_csv_cell
from app.routers.export import get_eligible_consenting_pids
from app.schemas.admin import (
    AdminBulkEnrolmentRequest,
    AdminBulkEnrolmentResponse,
    AdminConsentCoverageResponse,
    AdminConsentNoticeHistoryItem,
    AdminConsentSummary,
    AdminCourseConsentBreakdown,
    AdminCourseLecturerUpdate,
    AdminCoursePublishUpdate,
    AdminCourseSummary,
    AdminEnrolmentCreateRequest,
    AdminEnrolmentItem,
    AdminEnrolmentSummary,
    AdminExportHistoryItem,
    AdminIdentityRevealRequest,
    AdminIdentityRevealResponse,
    AdminIngestionRunItem,
    AdminIngestionStatusResponse,
    AdminMigrationItem,
    AdminOverviewResponse,
    AdminPaginatedCoursesResponse,
    AdminPaginatedEnrolmentsResponse,
    AdminPaginatedExportHistoryResponse,
    AdminPaginatedIngestionRunsResponse,
    AdminPaginatedRevealHistoryResponse,
    AdminPaginatedUsersResponse,
    AdminRevealHistoryItem,
    AdminScrubTestRequest,
    AdminScrubTestResponse,
    AdminSystemHealthResponse,
    AdminUserCreateRequest,
    AdminUserDetailResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    BulkEnrolmentRowResult,
    ComponentIngestionHealth,
    SystemStatsResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.profile import ProfileResponse
from app.services.audit import log_event

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


# ── GET /api/v1/admin/stats (Legacy backward compatibility) ───────────────────

@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get system-wide platform statistics",
    description="Returns aggregate counts from MongoDB users and courses collections.",
    dependencies=[Depends(get_current_admin)],
)
async def get_system_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SystemStatsResponse:
    total_users = await db[col.USERS].count_documents({})
    active_users = await db[col.USERS].count_documents({"is_active": True})
    total_students = await db[col.USERS].count_documents({"role": "student"})
    total_lecturers = await db[col.USERS].count_documents({"role": "lecturer"})

    total_courses = await db[col.COURSES].count_documents({})
    published_courses = await db[col.COURSES].count_documents({"is_published": True})

    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_courses=total_courses,
        published_courses=published_courses,
        total_students=total_students,
        total_lecturers=total_lecturers,
    )


# ── GET /api/v1/admin/overview ────────────────────────────────────────────────

@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Get consolidated admin overview and KPI metrics",
    description="Returns cross-platform operational health, consent coverage, pipeline, and ingestion status.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def get_admin_overview(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminOverviewResponse:
    # 1. Users metrics
    total_users = await db[col.USERS].count_documents({})
    active_users = await db[col.USERS].count_documents({"is_active": True})
    suspended_users = await db[col.USERS].count_documents({"is_active": False})

    roles_list = [r.value for r in UserRole]
    users_by_role: Dict[str, int] = {}
    for r in roles_list:
        users_by_role[r] = await db[col.USERS].count_documents({"role": r})

    # 2. Courses metrics
    total_courses = await db[col.COURSES].count_documents({})
    published_courses = await db[col.COURSES].count_documents({"is_published": True})
    draft_courses = max(0, total_courses - published_courses)

    # 3. Enrolments metrics
    total_enrolments = await db[col.ENROLMENTS].count_documents({})

    # 4. Consent Coverage (Feature 6)
    active_notice_doc = await db[col.CONSENT_NOTICES].find_one({"is_active": True})
    active_version = active_notice_doc.get("version") if active_notice_doc else None

    student_users = await db[col.USERS].find({"role": "student", "is_active": True}).to_list(length=10000)
    total_students = len(student_users)
    student_pids = [u["pid"] for u in student_users if u.get("pid")]

    accepted_consent = 0
    withdrawn_consent = 0
    declined_consent = 0
    pending_consent = total_students
    coverage_pct = 0.0

    if active_version and student_pids:
        pipeline = [
            {"$match": {"notice_version": active_version, "pid": {"$in": student_pids}}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$pid",
                    "latest_decision": {"$first": "$decision"},
                }
            },
        ]
        decisions_cursor = db[col.CONSENT_RECORDS].aggregate(pipeline)
        decisions_map: Dict[str, str] = {}
        async for doc in decisions_cursor:
            if doc.get("_id"):
                decisions_map[doc["_id"]] = doc.get("latest_decision", "")

        accepted_consent = 0
        withdrawn_consent = 0
        declined_consent = 0
        pending_consent = 0

        for s in student_users:
            pid = s.get("pid")
            dec = decisions_map.get(pid)
            if dec == "accepted":
                accepted_consent += 1
            elif dec == "withdrawn":
                withdrawn_consent += 1
            elif dec == "declined":
                declined_consent += 1
            else:
                pending_consent += 1

        coverage_pct = round((accepted_consent / total_students * 100.0), 1) if total_students > 0 else 0.0

    consent_stats = {
        "total_students": total_students,
        "accepted": accepted_consent,
        "declined": declined_consent,
        "withdrawn": withdrawn_consent,
        "pending": pending_consent,
        "coverage_percentage": coverage_pct,
    }

    # 5. Pipeline Summary (Feature 22)
    latest_pipeline_run = await db[col.PIPELINE_RUNS].find_one({}, sort=[("created_at", -1)])
    active_pipeline_runs = await db[col.PIPELINE_RUNS].count_documents({"overall_status": "running"})
    pipeline_summary: Dict[str, Any] = {
        "active_runs_count": active_pipeline_runs,
        "latest_run": None,
    }
    if latest_pipeline_run:
        pipeline_summary["latest_run"] = {
            "course_id": latest_pipeline_run.get("course_id"),
            "week_index": latest_pipeline_run.get("week_index"),
            "overall_status": latest_pipeline_run.get("overall_status"),
            "current_stage": latest_pipeline_run.get("current_stage"),
            "created_at": latest_pipeline_run.get("created_at"),
            "updated_at": latest_pipeline_run.get("updated_at"),
        }

    # 6. Ingestion Summary (Feature 23 / 24)
    ingestion_components = ["c1_affective", "c2_trajectory", "c3_risk", "c4_intervention"]
    ingestion_summary: Dict[str, Any] = {}
    for comp in ingestion_components:
        comp_prefix = comp.split("_")[0]
        comp_key_configured = bool(settings.COMPONENT_API_KEYS.get(comp_prefix))
        latest_ingest = await db[col.INGESTION_RUNS].find_one(
            {"component": {"$in": [comp, comp_prefix]}},
            sort=[("started_at", -1)],
        )
        ingestion_summary[comp_prefix] = {
            "component": comp,
            "configured": comp_key_configured,
            "last_run": latest_ingest.get("started_at") if latest_ingest else None,
            "status": latest_ingest.get("status") if latest_ingest else "idle",
            "records_processed": latest_ingest.get("records_processed", 0) if latest_ingest else 0,
        }

    # 7. Recent Audit Events (Feature 7)
    recent_logs_cursor = db[col.AUDIT_LOGS].find({}).sort("timestamp", -1).limit(10)
    raw_logs = await recent_logs_cursor.to_list(length=10)
    recent_audit_events: List[Dict[str, Any]] = []
    for log in raw_logs:
        recent_audit_events.append({
            "id": str(log.get("_id") or log.get("id")),
            "timestamp": log.get("timestamp"),
            "action": log.get("action"),
            "actor_id": log.get("actor_id"),
            "actor_role": log.get("actor_role"),
            "outcome": log.get("outcome"),
            "target_type": log.get("target_type"),
            "target_id": log.get("target_id"),
            "ip_address": log.get("ip_address"),
        })

    # 8. Database Health & Ping
    ping_start = time.perf_counter()
    db_status = "connected"
    try:
        await db.command("ping")
        ping_ms = round((time.perf_counter() - ping_start) * 1000, 2)
    except Exception as exc:
        db_status = f"unhealthy: {exc}"
        ping_ms = -1.0

    database_health = {
        "status": db_status,
        "ping_ms": ping_ms,
        "database_name": db.name,
    }

    return AdminOverviewResponse(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        users_by_role=users_by_role,
        total_courses=total_courses,
        published_courses=published_courses,
        draft_courses=draft_courses,
        total_enrolments=total_enrolments,
        consent_coverage=consent_stats,
        pipeline_summary=pipeline_summary,
        ingestion_summary=ingestion_summary,
        recent_audit_events=recent_audit_events,
        database_health=database_health,
    )


# ── GET /api/v1/admin/users ───────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=AdminPaginatedUsersResponse,
    summary="List platform users with server-side pagination and filters",
    description="Returns filtered, searchable, and paginated user accounts.",
    dependencies=[Depends(get_current_admin)],
)
async def list_admin_users(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search keyword in full_name or email"),
    role: Optional[str] = Query(None, description="Filter by user role or 'all'"),
    status: Optional[str] = Query(None, description="Filter by status: 'active', 'suspended', or 'all'"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: 'asc' or 'desc'"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedUsersResponse:
    query: Dict[str, Any] = {}

    if q and q.strip():
        term = re.escape(q.strip())
        query["$or"] = [
            {"full_name": {"$regex": term, "$options": "i"}},
            {"email": {"$regex": term, "$options": "i"}},
            {"pid": {"$regex": term, "$options": "i"}},
        ]

    if role and role.strip() and role != "all":
        query["role"] = role.strip()

    if status and status.strip() and status != "all":
        if status.lower() == "active":
            query["is_active"] = True
        elif status.lower() == "suspended":
            query["is_active"] = False

    direction = -1 if sort_order.lower() == "desc" else 1
    sort_field = sort_by if sort_by in ["created_at", "full_name", "email", "role", "is_active"] else "created_at"

    total = await db[col.USERS].count_documents(query)
    total_pages = max(1, (total + page_size - 1) // page_size)

    skip = (page - 1) * page_size
    cursor = db[col.USERS].find(query).sort(sort_field, direction).skip(skip).limit(page_size)
    user_docs = await cursor.to_list(length=page_size)

    items: List[AdminUserResponse] = []
    for doc in user_docs:
        # Standardize id
        doc_id = str(doc.get("_id") or doc.get("id"))
        doc["id"] = doc_id
        items.append(AdminUserResponse(**doc))

    return AdminPaginatedUsersResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── POST /api/v1/admin/users ──────────────────────────────────────────────────

@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account with temporary password",
    description="Provisions a user account in MongoDB, deterministic PID if student, and logs an audit event.",
    dependencies=[Depends(get_current_admin)],
)
async def create_user_by_admin(
    body: AdminUserCreateRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    # 1. Duplicate email check
    email_clean = body.email.lower().strip()
    existing_user = await db[col.USERS].find_one({"email": {"$regex": f"^{re.escape(email_clean)}$", "$options": "i"}})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{body.email}' already exists.",
        )

    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    role_val = body.role.value if hasattr(body.role, "value") else str(body.role)

    # 2. Construct profile
    profile_data = {
        "user_id": uid,
        "full_name": body.full_name.strip(),
        "email": email_clean,
        "phone": body.phone.strip() if body.phone else None,
        "bio": body.bio.strip() if body.bio else None,
        "department": body.department.strip() if body.department else None,
        "created_at": now,
        "updated_at": now,
    }

    user_doc: Dict[str, Any] = {
        "_id": uid,
        "id": uid,
        "email": email_clean,
        "hashed_password": hash_password(body.password),
        "full_name": body.full_name.strip(),
        "role": role_val,
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
        "profile": profile_data,
    }

    # 3. Deterministic PID and Identity Vault registration for students
    if role_val == "student":
        student_id = f"IT{abs(hash(uid)) % 100000000:08d}"
        pid = pseudonymize(student_id)
        user_doc["student_id"] = student_id
        user_doc["pid"] = pid

        vault_record = {
            "pid": pid,
            "student_id": student_id,
            "name": body.full_name.strip(),
            "email": email_clean,
            "created_at": now,
        }
        await db[col.IDENTITY_VAULT].update_one(
            {"_id": pid},
            {"$setOnInsert": vault_record},
            upsert=True,
        )

    await db[col.USERS].insert_one(user_doc)

    # 4. Write immutable audit log
    await log_event(
        request=request,
        db=db,
        action=AuditAction.USER_CREATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="user",
        target_id=uid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "created_role": role_val,
            "email_domain": email_clean.split("@")[-1],
            "has_profile": True,
        },
    )

    user_doc["id"] = uid
    return AdminUserResponse(**user_doc)


# ── GET /api/v1/admin/users/{user_id} ─────────────────────────────────────────

@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Get user detail drawer data",
    description="Returns detailed profile, pseudonym PID, enrolments, and consent posture.",
    dependencies=[Depends(get_current_admin)],
)
async def get_admin_user_detail(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserDetailResponse:
    uid_str = str(user_id).strip()
    user_doc = await db[col.USERS].find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db[col.USERS].find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found.",
        )

    # 1. Enrolments summary
    pid = user_doc.get("pid")
    enrolment_query = {"$or": [{"user_id": uid_str}]}
    if pid:
        enrolment_query["$or"].append({"student_pid": pid})

    enrolment_docs = await db[col.ENROLMENTS].find(enrolment_query).to_list(length=100)
    enrolments_list: List[AdminEnrolmentSummary] = []

    for enr in enrolment_docs:
        cid = str(enr.get("course_id", ""))
        course_doc = await db[col.COURSES].find_one({"_id": cid}) or await db[col.COURSES].find_one({"id": cid})
        course_name = course_doc.get("title") or course_doc.get("name") if course_doc else None
        course_code = course_doc.get("code") if course_doc else None

        enrolments_list.append(
            AdminEnrolmentSummary(
                course_id=cid,
                course_name=course_name,
                course_code=course_code,
                enrolled_at=enr.get("enrolled_at") or enr.get("created_at"),
                status=enr.get("status", "active"),
            )
        )

    # 2. Consent posture summary (Feature 6)
    consent_summary: Optional[AdminConsentSummary] = None
    if pid or user_doc.get("role") == "student":
        consent_query = {"$or": [{"user_id": uid_str}]}
        if pid:
            consent_query["$or"].append({"pid": pid})

        latest_consent = await db[col.CONSENT_RECORDS].find_one(
            consent_query,
            sort=[("decided_at", -1), ("timestamp", -1)],
        )
        if latest_consent:
            consent_summary = AdminConsentSummary(
                has_decision=True,
                decision=latest_consent.get("status") or latest_consent.get("decision"),
                decided_at=latest_consent.get("decided_at") or latest_consent.get("timestamp"),
                notice_version=latest_consent.get("notice_version") or latest_consent.get("version"),
            )
        else:
            consent_summary = AdminConsentSummary(has_decision=False)

    doc_id = str(user_doc.get("_id") or user_doc.get("id"))
    user_doc["id"] = doc_id

    return AdminUserDetailResponse(
        id=doc_id,
        email=user_doc.get("email"),
        full_name=user_doc.get("full_name"),
        role=user_doc.get("role"),
        is_active=user_doc.get("is_active", True),
        is_verified=user_doc.get("is_verified", False),
        created_at=user_doc.get("created_at"),
        updated_at=user_doc.get("updated_at"),
        pid=pid,
        profile=user_doc.get("profile"),
        enrolments=enrolments_list,
        consent=consent_summary,
    )


# ── PUT /api/v1/admin/users/{user_id}/status ──────────────────────────────────

@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update user active/suspended status with audit and last-admin safeguard",
    description="Activates or suspends a user account in MongoDB, blocking self-lockout and last-admin deactivation.",
    dependencies=[Depends(get_current_admin)],
)
async def update_user_status(
    user_id: str,
    body: UserStatusUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    uid_str = str(user_id).strip()
    user_doc = await db[col.USERS].find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db[col.USERS].find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found.",
        )

    # 1. Prevent administrators from suspending their own account
    if str(user_doc.get("_id")) == str(current_admin.id) and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own active account.",
        )

    # 2. Prevent suspending the LAST ACTIVE ADMINISTRATOR on the platform
    if user_doc.get("role") == UserRole.ADMIN.value and not body.is_active:
        active_admin_count = await db[col.USERS].count_documents({"role": UserRole.ADMIN.value, "is_active": True})
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot suspend the last active administrator on the platform.",
            )

    previous_is_active = user_doc.get("is_active", True)
    now = datetime.now(timezone.utc)
    updated_doc = await db[col.USERS].find_one_and_update(
        {"_id": user_doc["_id"]},
        {"$set": {"is_active": body.is_active, "updated_at": now}},
        return_document=True,
    )

    # 3. Log Feature 7 compliance audit event
    await log_event(
        request=request,
        db=db,
        action=AuditAction.USER_STATUS_UPDATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="user",
        target_id=uid_str,
        outcome=AuditOutcome.SUCCESS,
        details={
            "previous_is_active": previous_is_active,
            "new_is_active": body.is_active,
            "target_role": user_doc.get("role"),
        },
    )

    updated_doc["id"] = str(updated_doc.get("_id") or updated_doc.get("id"))
    return AdminUserResponse(**updated_doc)


# ── PUT /api/v1/admin/users/{user_id}/role ────────────────────────────────────

@router.put(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Update user authorization role with audit and last-admin safeguard",
    description="Assigns a new role, enforcing self-demotion prevention and last-admin demotion prevention.",
    dependencies=[Depends(get_current_admin)],
)
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    uid_str = str(user_id).strip()
    user_doc = await db[col.USERS].find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db[col.USERS].find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found.",
        )

    role_val = body.role.value if hasattr(body.role, "value") else str(body.role)
    current_user_role = user_doc.get("role")

    # 1. Prevent admin from removing their own admin status
    if str(user_doc.get("_id")) == str(current_admin.id) and role_val != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account role.",
        )

    # 2. Prevent demoting the LAST ACTIVE ADMINISTRATOR on the platform
    if current_user_role == UserRole.ADMIN.value and role_val != UserRole.ADMIN.value:
        active_admin_count = await db[col.USERS].count_documents({"role": UserRole.ADMIN.value, "is_active": True})
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active administrator on the platform.",
            )

    now = datetime.now(timezone.utc)
    update_fields: Dict[str, Any] = {"role": role_val, "updated_at": now}

    # If role changed to student and user doesn't have a PID yet:
    if role_val == "student" and not user_doc.get("pid"):
        student_id = user_doc.get("student_id") or f"IT{abs(hash(uid_str)) % 100000000:08d}"
        pid = pseudonymize(student_id)
        update_fields["student_id"] = student_id
        update_fields["pid"] = pid

        vault_record = {
            "pid": pid,
            "student_id": student_id,
            "name": user_doc.get("full_name"),
            "email": user_doc.get("email"),
            "created_at": now,
        }
        await db[col.IDENTITY_VAULT].update_one(
            {"_id": pid},
            {"$setOnInsert": vault_record},
            upsert=True,
        )

    updated_doc = await db[col.USERS].find_one_and_update(
        {"_id": user_doc["_id"]},
        {"$set": update_fields},
        return_document=True,
    )

    # 3. Log Feature 7 compliance audit event
    await log_event(
        request=request,
        db=db,
        action=AuditAction.USER_ROLE_UPDATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="user",
        target_id=uid_str,
        outcome=AuditOutcome.SUCCESS,
        details={
            "previous_role": current_user_role,
            "new_role": role_val,
        },
    )

    updated_doc["id"] = str(updated_doc.get("_id") or updated_doc.get("id"))
    return AdminUserResponse(**updated_doc)


# ── PUT /api/v1/admin/users/{user_id}/profile ─────────────────────────────────

@router.put(
    "/users/{user_id}/profile",
    response_model=AdminUserResponse,
    summary="Update editable profile fields of a user",
    description="Updates user profile attributes (full_name, phone, bio, department) with audit logging.",
    dependencies=[Depends(get_current_admin)],
)
async def update_user_profile_by_admin(
    user_id: str,
    body: AdminUserUpdateRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminUserResponse:
    uid_str = str(user_id).strip()
    user_doc = await db[col.USERS].find_one({"_id": uid_str})
    if not user_doc:
        user_doc = await db[col.USERS].find_one({"id": uid_str})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found.",
        )

    now = datetime.now(timezone.utc)
    set_fields: Dict[str, Any] = {"updated_at": now}

    profile_dict = user_doc.get("profile") or {
        "user_id": uid_str,
        "email": user_doc.get("email"),
        "full_name": user_doc.get("full_name"),
    }

    if body.full_name is not None and body.full_name.strip():
        name_clean = body.full_name.strip()
        set_fields["full_name"] = name_clean
        profile_dict["full_name"] = name_clean

    if body.phone is not None:
        profile_dict["phone"] = body.phone.strip() if body.phone else None
    if body.bio is not None:
        profile_dict["bio"] = body.bio.strip() if body.bio else None
    if body.department is not None:
        profile_dict["department"] = body.department.strip() if body.department else None

    profile_dict["updated_at"] = now
    set_fields["profile"] = profile_dict

    updated_doc = await db[col.USERS].find_one_and_update(
        {"_id": user_doc["_id"]},
        {"$set": set_fields},
        return_document=True,
    )

    # Audit logging
    await log_event(
        request=request,
        db=db,
        action=AuditAction.USER_PROFILE_UPDATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="user",
        target_id=uid_str,
        outcome=AuditOutcome.SUCCESS,
        details={
            "updated_fields": list(body.model_dump(exclude_unset=True).keys()),
        },
    )

    updated_doc["id"] = str(updated_doc.get("_id") or updated_doc.get("id"))
    return AdminUserResponse(**updated_doc)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: Courses Oversight & Administration
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/courses",
    response_model=AdminPaginatedCoursesResponse,
    summary="List courses with admin metadata, pagination, and filters",
    description="Returns courses enriched with instructor profile, enrolled student count, and module counts.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def list_admin_courses(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query matching title or code"),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    lecturer_id: Optional[str] = Query(None, description="Filter by instructor ID"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedCoursesResponse:
    filter_doc: Dict[str, Any] = {}

    if is_published is not None:
        filter_doc["is_published"] = is_published

    if lecturer_id:
        filter_doc["lecturer_id"] = str(lecturer_id).strip()

    if q and q.strip():
        q_clean = q.strip()
        regex = re.compile(re.escape(q_clean), re.IGNORECASE)
        filter_doc["$or"] = [
            {"title": regex},
            {"description": regex},
            {"course_id": regex},
            {"id": regex},
            {"_id": regex},
        ]

    total = await db[col.COURSES].count_documents(filter_doc)
    skip = (page - 1) * page_size
    cursor = db[col.COURSES].find(filter_doc).sort("created_at", -1).skip(skip).limit(page_size)
    courses_docs = await cursor.to_list(length=page_size)

    if not courses_docs:
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return AdminPaginatedCoursesResponse(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # 1. Batch resolve instructors
    lecturer_ids = list({str(c["lecturer_id"]) for c in courses_docs if c.get("lecturer_id")})
    lecturer_map: Dict[str, Dict[str, Any]] = {}
    if lecturer_ids:
        lecturers_cursor = db[col.USERS].find({
            "$or": [{"_id": {"$in": lecturer_ids}}, {"id": {"$in": lecturer_ids}}]
        })
        async for l_doc in lecturers_cursor:
            l_info = {
                "name": l_doc.get("full_name") or "Unknown Lecturer",
                "email": l_doc.get("email") or "",
            }
            lecturer_map[str(l_doc.get("_id"))] = l_info
            if l_doc.get("id"):
                lecturer_map[str(l_doc.get("id"))] = l_info

    # 2. Batch resolve active enrolment count per course
    c_keys = []
    for c in courses_docs:
        c_keys.append(str(c.get("course_id") or c.get("id") or c.get("_id")))
        c_keys.append(str(c["_id"]))
        if c.get("id"):
            c_keys.append(str(c["id"]))
    c_keys = list(set(c_keys))

    enrolment_map: Dict[str, int] = {}
    pipeline = [
        {"$match": {"course_id": {"$in": c_keys}, "status": "active"}},
        {"$group": {"_id": "$course_id", "count": {"$sum": 1}}},
    ]
    async for agg in db[col.ENROLMENTS].aggregate(pipeline):
        enrolment_map[str(agg["_id"])] = agg["count"]

    items: List[AdminCourseSummary] = []
    for c in courses_docs:
        canonical_cid = str(c.get("course_id") or c.get("id") or c.get("_id"))
        lid = str(c.get("lecturer_id")) if c.get("lecturer_id") else None
        linfo = lecturer_map.get(lid, {}) if lid else {}
        active_enrolled = (
            enrolment_map.get(canonical_cid, 0)
            or enrolment_map.get(str(c.get("_id")), 0)
            or enrolment_map.get(str(c.get("id")), 0)
        )

        items.append(
            AdminCourseSummary(
                id=str(c.get("_id") or c.get("id") or canonical_cid),
                course_id=canonical_cid,
                title=c.get("title", "Untitled Course"),
                description=c.get("description"),
                lecturer_id=lid,
                lecturer_name=linfo.get("name"),
                lecturer_email=linfo.get("email"),
                is_published=c.get("is_published", True),
                enrolment_count=active_enrolled,
                module_count=len(c.get("modules") or []),
                created_at=c.get("created_at"),
                updated_at=c.get("updated_at"),
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return AdminPaginatedCoursesResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put(
    "/courses/{course_id}/publish",
    response_model=AdminCourseSummary,
    summary="Publish or unpublish course with Feature 7 audit logging",
    description="Updates visibility in the course catalog and records before/after state in audit log.",
    dependencies=[Depends(get_current_admin)],
)
async def update_course_publish_status(
    course_id: str,
    body: AdminCoursePublishUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminCourseSummary:
    cid_str = str(course_id).strip()
    course_doc = await db[col.COURSES].find_one({
        "$or": [{"_id": cid_str}, {"id": cid_str}, {"course_id": cid_str}]
    })
    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' was not found.",
        )

    previous_is_published = course_doc.get("is_published", False)
    now = datetime.now(timezone.utc)

    updated_doc = await db[col.COURSES].find_one_and_update(
        {"_id": course_doc["_id"]},
        {"$set": {"is_published": body.is_published, "updated_at": now}},
        return_document=True,
    )

    canonical_cid = str(updated_doc.get("course_id") or updated_doc.get("id") or updated_doc.get("_id"))

    # Feature 7 Audit Logging
    await log_event(
        request=request,
        db=db,
        action=AuditAction.COURSE_STATUS_UPDATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="course",
        target_id=canonical_cid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "previous_is_published": previous_is_published,
            "new_is_published": body.is_published,
        },
    )

    # Resolve instructor name/email if present
    lid = str(updated_doc.get("lecturer_id")) if updated_doc.get("lecturer_id") else None
    linfo: Dict[str, Any] = {}
    if lid:
        ldoc = await db[col.USERS].find_one({"$or": [{"_id": lid}, {"id": lid}]})
        if ldoc:
            linfo = {"name": ldoc.get("full_name"), "email": ldoc.get("email")}

    enrolment_count = await db[col.ENROLMENTS].count_documents({
        "course_id": canonical_cid,
        "status": "active",
    })

    return AdminCourseSummary(
        id=str(updated_doc.get("_id") or updated_doc.get("id") or canonical_cid),
        course_id=canonical_cid,
        title=updated_doc.get("title", "Untitled Course"),
        description=updated_doc.get("description"),
        lecturer_id=lid,
        lecturer_name=linfo.get("name"),
        lecturer_email=linfo.get("email"),
        is_published=updated_doc.get("is_published", True),
        enrolment_count=enrolment_count,
        module_count=len(updated_doc.get("modules") or []),
        created_at=updated_doc.get("created_at"),
        updated_at=updated_doc.get("updated_at"),
    )


@router.put(
    "/courses/{course_id}/lecturer",
    response_model=AdminCourseSummary,
    summary="Assign or reassign course instructor with Feature 7 audit logging",
    description="Validates instructor account existence and active state, then records assignment in audit log.",
    dependencies=[Depends(get_current_admin)],
)
async def reassign_course_lecturer(
    course_id: str,
    body: AdminCourseLecturerUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminCourseSummary:
    cid_str = str(course_id).strip()
    course_doc = await db[col.COURSES].find_one({
        "$or": [{"_id": cid_str}, {"id": cid_str}, {"course_id": cid_str}]
    })
    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' was not found.",
        )

    target_lecturer_id = str(body.lecturer_id).strip()
    lecturer_doc = await db[col.USERS].find_one({
        "$or": [{"_id": target_lecturer_id}, {"id": target_lecturer_id}]
    })
    if not lecturer_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instructor account with ID '{body.lecturer_id}' does not exist.",
        )
    if not lecturer_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign course to a deactivated instructor account.",
        )

    previous_lecturer_id = str(course_doc.get("lecturer_id")) if course_doc.get("lecturer_id") else "unassigned"
    now = datetime.now(timezone.utc)

    updated_doc = await db[col.COURSES].find_one_and_update(
        {"_id": course_doc["_id"]},
        {"$set": {"lecturer_id": target_lecturer_id, "updated_at": now}},
        return_document=True,
    )

    canonical_cid = str(updated_doc.get("course_id") or updated_doc.get("id") or updated_doc.get("_id"))

    # Feature 7 Audit Logging (no emails or names in details)
    await log_event(
        request=request,
        db=db,
        action=AuditAction.COURSE_LECTURER_ASSIGNED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="course",
        target_id=canonical_cid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "previous_lecturer_id": previous_lecturer_id,
            "new_lecturer_id": target_lecturer_id,
        },
    )

    enrolment_count = await db[col.ENROLMENTS].count_documents({
        "course_id": canonical_cid,
        "status": "active",
    })

    return AdminCourseSummary(
        id=str(updated_doc.get("_id") or updated_doc.get("id") or canonical_cid),
        course_id=canonical_cid,
        title=updated_doc.get("title", "Untitled Course"),
        description=updated_doc.get("description"),
        lecturer_id=target_lecturer_id,
        lecturer_name=lecturer_doc.get("full_name"),
        lecturer_email=lecturer_doc.get("email"),
        is_published=updated_doc.get("is_published", True),
        enrolment_count=enrolment_count,
        module_count=len(updated_doc.get("modules") or []),
        created_at=updated_doc.get("created_at"),
        updated_at=updated_doc.get("updated_at"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: Enrolments Administration
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/enrolments",
    response_model=AdminPaginatedEnrolmentsResponse,
    summary="List course enrolments with student/course details and filters",
    description="Returns student enrolments enriched with student name/email and course title.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def list_admin_enrolments(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    pid: Optional[str] = Query(None, description="Filter by pseudonym identifier (PID)"),
    status: Optional[str] = Query(None, description="Filter by enrolment status ('active', 'dropped', or 'all')"),
    q: Optional[str] = Query(None, description="Search by student name, email, or course title"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedEnrolmentsResponse:
    filter_doc: Dict[str, Any] = {}

    if course_id:
        filter_doc["course_id"] = str(course_id).strip()

    if pid:
        filter_doc["pid"] = str(pid).strip()

    if student_id:
        sid_str = str(student_id).strip()
        user_match = await db[col.USERS].find_one({"$or": [{"_id": sid_str}, {"id": sid_str}]})
        if user_match and user_match.get("pid"):
            filter_doc["pid"] = user_match["pid"]
        else:
            filter_doc["$or"] = [{"student_id": sid_str}, {"pid": sid_str}]

    if status and status.lower() != "all":
        filter_doc["status"] = status.lower()

    if q and q.strip():
        q_clean = q.strip()
        # Find matching course IDs
        matched_courses = await db[col.COURSES].find({
            "$or": [
                {"title": {"$regex": q_clean, "$options": "i"}},
                {"course_id": {"$regex": q_clean, "$options": "i"}},
            ]
        }).to_list(100)
        matched_cids = [str(c.get("course_id") or c.get("id") or c["_id"]) for c in matched_courses]
        matched_cids.extend([str(c["_id"]) for c in matched_courses])

        # Find matching student PIDs
        matched_users = await db[col.USERS].find({
            "$or": [
                {"full_name": {"$regex": q_clean, "$options": "i"}},
                {"email": {"$regex": q_clean, "$options": "i"}},
                {"pid": {"$regex": q_clean, "$options": "i"}},
            ]
        }).to_list(100)
        matched_pids = [u["pid"] for u in matched_users if u.get("pid")]

        q_clauses: List[Dict[str, Any]] = []
        if matched_cids:
            q_clauses.append({"course_id": {"$in": list(set(matched_cids))}})
        if matched_pids:
            q_clauses.append({"pid": {"$in": list(set(matched_pids))}})
        if not q_clauses:
            # Query will match nothing
            q_clauses.append({"pid": "__no_match__"})

        if "$or" in filter_doc:
            filter_doc["$and"] = [{"$or": filter_doc.pop("$or")}, {"$or": q_clauses}]
        else:
            filter_doc["$or"] = q_clauses

    total = await db[col.ENROLMENTS].count_documents(filter_doc)
    skip = (page - 1) * page_size
    cursor = db[col.ENROLMENTS].find(filter_doc).sort("enrolment_start", -1).skip(skip).limit(page_size)
    enrolments_docs = await cursor.to_list(length=page_size)

    if not enrolments_docs:
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return AdminPaginatedEnrolmentsResponse(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # 1. Batch resolve courses
    cids = list({e["course_id"] for e in enrolments_docs if e.get("course_id")})
    courses_map: Dict[str, str] = {}
    if cids:
        c_cursor = db[col.COURSES].find({
            "$or": [{"_id": {"$in": cids}}, {"id": {"$in": cids}}, {"course_id": {"$in": cids}}]
        })
        async for c in c_cursor:
            title = c.get("title", "Untitled Course")
            courses_map[str(c["_id"])] = title
            if c.get("id"):
                courses_map[str(c["id"])] = title
            if c.get("course_id"):
                courses_map[str(c["course_id"])] = title

    # 2. Batch resolve students by PID
    pids = list({e["pid"] for e in enrolments_docs if e.get("pid")})
    student_map: Dict[str, Dict[str, Any]] = {}
    if pids:
        u_cursor = db[col.USERS].find({"pid": {"$in": pids}})
        async for u in u_cursor:
            student_map[u["pid"]] = {
                "id": str(u["_id"]),
                "name": u.get("full_name") or "Unknown Student",
                "email": u.get("email") or "",
            }

    items: List[AdminEnrolmentItem] = []
    for enr in enrolments_docs:
        pid_val = enr.get("pid")
        cid_val = enr.get("course_id")
        sinfo = student_map.get(pid_val, {}) if pid_val else {}

        items.append(
            AdminEnrolmentItem(
                id=str(enr["_id"]),
                course_id=cid_val,
                course_title=courses_map.get(cid_val),
                student_id=sinfo.get("id"),
                student_name=sinfo.get("name"),
                student_email=sinfo.get("email"),
                pid=pid_val,
                status=enr.get("status", "active"),
                enrolled_at=enr.get("enrolment_start"),
                enrolment_end=enr.get("enrolment_end"),
                updated_at=enr.get("updated_at") or enr.get("enrolment_start"),
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return AdminPaginatedEnrolmentsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/enrolments",
    response_model=AdminEnrolmentItem,
    status_code=status.HTTP_201_CREATED,
    summary="Enrol student into course with deterministic PID and audit log",
    description="Idempotent: Enrols a student by email, ID, or PID. Writes Feature 7 audit log.",
    dependencies=[Depends(get_current_admin)],
)
async def create_admin_enrolment(
    body: AdminEnrolmentCreateRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminEnrolmentItem:
    # 1. Validate target course
    cid_str = str(body.course_id).strip()
    course_doc = await db[col.COURSES].find_one({
        "$or": [{"_id": cid_str}, {"id": cid_str}, {"course_id": cid_str}]
    })
    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{body.course_id}' was not found.",
        )
    canonical_cid = str(course_doc.get("course_id") or course_doc.get("id") or course_doc.get("_id"))

    # 2. Resolve student
    ident = str(body.student_identifier).strip()
    user_doc = await db[col.USERS].find_one({
        "$or": [
            {"_id": ident},
            {"id": ident},
            {"email": ident.lower()},
            {"pid": ident},
        ]
    })
    if not user_doc and ident.startswith("STU_"):
        vault_doc = await db[col.IDENTITY_VAULT].find_one({"_id": ident})
        if vault_doc and vault_doc.get("email"):
            user_doc = await db[col.USERS].find_one({"email": vault_doc["email"]})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student account matching '{body.student_identifier}' was not found.",
        )

    # Ensure student has a deterministic PID
    pid = user_doc.get("pid")
    now = datetime.now(timezone.utc)
    if not pid:
        student_id = user_doc.get("student_id") or f"IT{abs(hash(str(user_doc['_id']))) % 100000000:08d}"
        pid = pseudonymize(student_id)
        await db[col.USERS].update_one({"_id": user_doc["_id"]}, {"$set": {"pid": pid, "student_id": student_id}})
        vault_record = {
            "pid": pid,
            "student_id": student_id,
            "name": user_doc.get("full_name"),
            "email": user_doc.get("email"),
            "created_at": now,
        }
        await db[col.IDENTITY_VAULT].update_one({"_id": pid}, {"$setOnInsert": vault_record}, upsert=True)

    # 3. Check for existing enrolment (idempotent / reactivation)
    existing_enr = await db[col.ENROLMENTS].find_one({
        "course_id": canonical_cid,
        "pid": pid,
    })

    if existing_enr:
        if existing_enr.get("status") == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student is already actively enrolled in course '{course_doc.get('title')}'.",
            )
        # Reactivate dropped enrolment
        await db[col.ENROLMENTS].update_one(
            {"_id": existing_enr["_id"]},
            {"$set": {"status": "active", "enrolment_start": now, "enrolment_end": None}},
        )
        enr_id = str(existing_enr["_id"])
    else:
        enr_id = str(uuid.uuid4())
        new_enr_doc = {
            "_id": enr_id,
            "pid": pid,
            "course_id": canonical_cid,
            "enrolment_start": now,
            "status": "active",
            "schema_version": 1,
            "ingested_at": now,
            "source_version": "1.0",
        }
        await db[col.ENROLMENTS].insert_one(new_enr_doc)

    # 4. Feature 7: Audit Log
    await log_event(
        request=request,
        db=db,
        action=AuditAction.ENROLMENT_CREATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="student",
        target_id=pid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "course_id": canonical_cid,
            "status": "active",
        },
    )

    return AdminEnrolmentItem(
        id=enr_id,
        course_id=canonical_cid,
        course_title=course_doc.get("title"),
        student_id=str(user_doc["_id"]),
        student_name=user_doc.get("full_name"),
        student_email=user_doc.get("email"),
        pid=pid,
        status="active",
        enrolled_at=now,
    )


@router.delete(
    "/enrolments/{enrolment_id}",
    summary="Soft-unenrol a student from a course (Never deletes academic records)",
    description="Marks enrolment status as 'dropped' and records enrolment_end timestamp. Preserves all submissions, grades, and logs.",
    dependencies=[Depends(get_current_admin)],
)
async def remove_admin_enrolment(
    enrolment_id: str,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    eid_str = str(enrolment_id).strip()
    enr_doc = await db[col.ENROLMENTS].find_one({"_id": eid_str})
    if not enr_doc:
        enr_doc = await db[col.ENROLMENTS].find_one({"id": eid_str})

    if not enr_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrolment record '{enrolment_id}' was not found.",
        )

    previous_status = enr_doc.get("status", "active")
    now = datetime.now(timezone.utc)

    # CRITICAL: Soft-removal ONLY. NEVER delete student grades, attendance, or submissions!
    await db[col.ENROLMENTS].update_one(
        {"_id": enr_doc["_id"]},
        {"$set": {"status": "dropped", "enrolment_end": now}},
    )

    # Feature 7: Audit Log
    pid_target = enr_doc.get("pid") or "unknown"
    await log_event(
        request=request,
        db=db,
        action=AuditAction.ENROLMENT_REMOVED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="student",
        target_id=pid_target,
        outcome=AuditOutcome.SUCCESS,
        details={
            "course_id": enr_doc.get("course_id"),
            "previous_status": previous_status,
            "new_status": "dropped",
        },
    )

    return {
        "message": "Student enrolment successfully set to dropped. Academic records and history preserved.",
        "id": eid_str,
        "status": "dropped",
    }


@router.post(
    "/enrolments/bulk",
    response_model=AdminBulkEnrolmentResponse,
    summary="Idempotent bulk student enrolment with per-row breakdown",
    description="Processes an array of student emails, IDs, or PIDs. Enrols active students, skips existing, and reports failures.",
    dependencies=[Depends(get_current_admin)],
)
async def bulk_admin_enrolment(
    body: AdminBulkEnrolmentRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminBulkEnrolmentResponse:
    # 1. Validate course
    cid_str = str(body.course_id).strip()
    course_doc = await db[col.COURSES].find_one({
        "$or": [{"_id": cid_str}, {"id": cid_str}, {"course_id": cid_str}]
    })
    if not course_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{body.course_id}' was not found.",
        )
    canonical_cid = str(course_doc.get("course_id") or course_doc.get("id") or course_doc.get("_id"))

    enrolled_count = 0
    skipped_count = 0
    failed_count = 0
    results: List[BulkEnrolmentRowResult] = []
    now = datetime.now(timezone.utc)

    for raw_ident in body.student_identifiers:
        ident = str(raw_ident).strip()
        if not ident:
            continue

        # Look up user
        user_doc = await db[col.USERS].find_one({
            "$or": [
                {"email": ident.lower()},
                {"_id": ident},
                {"id": ident},
                {"pid": ident},
            ]
        })
        if not user_doc and ident.startswith("STU_"):
            vault_doc = await db[col.IDENTITY_VAULT].find_one({"_id": ident})
            if vault_doc and vault_doc.get("email"):
                user_doc = await db[col.USERS].find_one({"email": vault_doc["email"]})

        if not user_doc:
            failed_count += 1
            results.append(
                BulkEnrolmentRowResult(
                    identifier=ident,
                    status="failed",
                    reason="Student account not found on platform.",
                )
            )
            continue

        # Ensure PID exists
        pid = user_doc.get("pid")
        if not pid:
            student_id = user_doc.get("student_id") or f"IT{abs(hash(str(user_doc['_id']))) % 100000000:08d}"
            pid = pseudonymize(student_id)
            await db[col.USERS].update_one({"_id": user_doc["_id"]}, {"$set": {"pid": pid, "student_id": student_id}})
            vault_record = {
                "pid": pid,
                "student_id": student_id,
                "name": user_doc.get("full_name"),
                "email": user_doc.get("email"),
                "created_at": now,
            }
            await db[col.IDENTITY_VAULT].update_one({"_id": pid}, {"$setOnInsert": vault_record}, upsert=True)

        # Check existing enrolment
        existing_enr = await db[col.ENROLMENTS].find_one({
            "course_id": canonical_cid,
            "pid": pid,
        })

        if existing_enr and existing_enr.get("status") == "active":
            skipped_count += 1
            results.append(
                BulkEnrolmentRowResult(
                    identifier=ident,
                    status="skipped",
                    reason="Already actively enrolled in course.",
                    student_id=str(user_doc["_id"]),
                    pid=pid,
                )
            )
            continue
        elif existing_enr and existing_enr.get("status") != "active":
            # Reactivate
            await db[col.ENROLMENTS].update_one(
                {"_id": existing_enr["_id"]},
                {"$set": {"status": "active", "enrolment_start": now, "enrolment_end": None}},
            )
            enrolled_count += 1
            results.append(
                BulkEnrolmentRowResult(
                    identifier=ident,
                    status="enrolled",
                    student_id=str(user_doc["_id"]),
                    pid=pid,
                )
            )
        else:
            new_doc = {
                "_id": str(uuid.uuid4()),
                "pid": pid,
                "course_id": canonical_cid,
                "enrolment_start": now,
                "status": "active",
                "schema_version": 1,
                "ingested_at": now,
                "source_version": "1.0",
            }
            await db[col.ENROLMENTS].insert_one(new_doc)
            enrolled_count += 1
            results.append(
                BulkEnrolmentRowResult(
                    identifier=ident,
                    status="enrolled",
                    student_id=str(user_doc["_id"]),
                    pid=pid,
                )
            )

    # Feature 7: Audit Log (Never leak student identifiers in details)
    await log_event(
        request=request,
        db=db,
        action=AuditAction.BULK_ENROLMENT,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="course",
        target_id=canonical_cid,
        outcome=AuditOutcome.SUCCESS,
        details={
            "course_id": canonical_cid,
            "total_submitted": len(body.student_identifiers),
            "enrolled_count": enrolled_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        },
    )

    return AdminBulkEnrolmentResponse(
        course_id=canonical_cid,
        total=len(body.student_identifiers),
        enrolled_count=enrolled_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        results=results,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: Consent & Ethics Governance
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/consent/coverage",
    response_model=AdminConsentCoverageResponse,
    summary="Get active consent notice coverage, per-course breakdown, and version history",
    description=(
        "Measures consent coverage strictly against the active notice version. "
        "Withdrawn students are never counted as consented. Shows overall and per-course breakdown."
    ),
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def get_admin_consent_coverage(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminConsentCoverageResponse:
    # 1. Active notice
    active_notice_doc = await db[col.CONSENT_NOTICES].find_one({"is_active": True})
    active_notice_dict = None
    active_version: Optional[int] = None
    if active_notice_doc:
        active_version = active_notice_doc.get("version")
        active_notice_dict = {
            "id": str(active_notice_doc.get("_id") or active_notice_doc.get("id")),
            "version": active_version,
            "text": active_notice_doc.get("text", ""),
            "effective_from": active_notice_doc.get("effective_from"),
            "is_active": True,
        }

    # 2. Historical notice versions
    all_notices_cursor = db[col.CONSENT_NOTICES].find({}).sort("version", -1)
    notice_history: List[AdminConsentNoticeHistoryItem] = []
    async for n in all_notices_cursor:
        notice_history.append(
            AdminConsentNoticeHistoryItem(
                id=str(n.get("_id") or n.get("id")),
                version=n.get("version", 1),
                text=n.get("text", ""),
                effective_from=n.get("effective_from") or datetime.now(timezone.utc),
                is_active=n.get("is_active", False),
            )
        )

    # 3. Overall Student Posture
    student_users = await db[col.USERS].find({"role": "student", "is_active": True}).to_list(length=10000)
    total_students = len(student_users)
    student_pids = [u["pid"] for u in student_users if u.get("pid")]

    # If no active notice or no students
    if not active_version or not student_pids:
        return AdminConsentCoverageResponse(
            active_notice=active_notice_dict,
            active_version=active_version,
            total_students=total_students,
            accepted=0,
            withdrawn=0,
            declined=0,
            pending=total_students,
            coverage_percentage=0.0,
            course_breakdown=[],
            notice_history=notice_history,
        )

    # Aggregation for active notice version: latest decision per PID
    pipeline = [
        {"$match": {"notice_version": active_version, "pid": {"$in": student_pids}}},
        {"$sort": {"timestamp": -1}},
        {
            "$group": {
                "_id": "$pid",
                "latest_decision": {"$first": "$decision"},
            }
        },
    ]
    decisions_cursor = db[col.CONSENT_RECORDS].aggregate(pipeline)
    decisions_map: Dict[str, str] = {}
    async for doc in decisions_cursor:
        if doc.get("_id"):
            decisions_map[doc["_id"]] = doc.get("latest_decision", "")

    accepted_count = 0
    withdrawn_count = 0
    declined_count = 0
    pending_count = 0

    for s in student_users:
        pid = s.get("pid")
        dec = decisions_map.get(pid)
        if dec == "accepted":
            accepted_count += 1
        elif dec == "withdrawn":
            withdrawn_count += 1
        elif dec == "declined":
            declined_count += 1
        else:
            pending_count += 1

    coverage_pct = round((accepted_count / total_students * 100.0), 1) if total_students > 0 else 0.0

    # 4. Per-Course Breakdown
    courses_cursor = db[col.COURSES].find({}).sort("title", 1)
    courses_docs = await courses_cursor.to_list(length=200)

    course_breakdown: List[AdminCourseConsentBreakdown] = []
    for c in courses_docs:
        canonical_cid = str(c.get("course_id") or c.get("id") or c.get("_id"))
        enrs_cursor = db[col.ENROLMENTS].find({
            "course_id": {"$in": [canonical_cid, str(c["_id"])]},
            "status": "active",
        })
        enr_pids = [e["pid"] async for e in enrs_cursor if e.get("pid")]
        unique_enr_pids = list(set(enr_pids))
        course_enrolled_count = len(unique_enr_pids)

        c_accepted = sum(1 for p in unique_enr_pids if decisions_map.get(p) == "accepted")
        c_withdrawn = sum(1 for p in unique_enr_pids if decisions_map.get(p) == "withdrawn")
        c_declined = sum(1 for p in unique_enr_pids if decisions_map.get(p) == "declined")
        c_pending = max(0, course_enrolled_count - (c_accepted + c_withdrawn + c_declined))
        c_coverage = round((c_accepted / course_enrolled_count * 100.0), 1) if course_enrolled_count > 0 else 0.0

        course_breakdown.append(
            AdminCourseConsentBreakdown(
                course_id=canonical_cid,
                course_title=c.get("title", "Untitled Course"),
                enrolled_students=course_enrolled_count,
                accepted=c_accepted,
                withdrawn=c_withdrawn,
                declined=c_declined,
                pending=c_pending,
                coverage_percentage=c_coverage,
            )
        )

    return AdminConsentCoverageResponse(
        active_notice=active_notice_dict,
        active_version=active_version,
        total_students=total_students,
        accepted=accepted_count,
        withdrawn=withdrawn_count,
        declined=declined_count,
        pending=pending_count,
        coverage_percentage=coverage_pct,
        course_breakdown=course_breakdown,
        notice_history=notice_history,
    )


# ── Phase 3: Ingestion Health & Runs ──────────────────────────────────────────

@router.get(
    "/ingestion/status",
    response_model=AdminIngestionStatusResponse,
    summary="Get ML Component Ingestion Status & Health",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def get_admin_ingestion_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminIngestionStatusResponse:
    component_defs = [
        ("c1", "c1_affective", "C1 Affective Weekly"),
        ("c2", "c2_trajectory", "C2 Engagement Trajectory"),
        ("c3", "c3_risk", "C3 Multimodal Risk Assessment"),
        ("c4", "c4_intervention", "C4 Intervention Recommendations"),
    ]

    components: Dict[str, ComponentIngestionHealth] = {}
    for prefix, comp_name, title in component_defs:
        key_configured = bool(settings.COMPONENT_API_KEYS.get(prefix))

        latest_run = await db[col.INGESTION_RUNS].find_one(
            {"component": {"$in": [comp_name, prefix]}},
            sort=[("started_at", -1)],
        )
        latest_success = await db[col.INGESTION_RUNS].find_one(
            {"component": {"$in": [comp_name, prefix]}, "status": "success"},
            sort=[("started_at", -1)],
        )
        latest_failure = await db[col.INGESTION_RUNS].find_one(
            {"component": {"$in": [comp_name, prefix]}, "status": "failed"},
            sort=[("started_at", -1)],
        )

        pipeline = [
            {"$match": {"component": {"$in": [comp_name, prefix]}}},
            {
                "$group": {
                    "_id": None,
                    "total_accepted": {"$sum": "$records_accepted"},
                    "total_rejected": {"$sum": "$records_rejected"},
                    "total_processed": {"$sum": "$records_processed"},
                }
            },
        ]
        agg_cursor = db[col.INGESTION_RUNS].aggregate(pipeline)
        agg_docs = await agg_cursor.to_list(length=1)
        totals = agg_docs[0] if agg_docs else {}

        last_err = None
        if latest_failure:
            last_err = latest_failure.get("error_message") or (
                latest_failure.get("errors", [{}])[0].get("message")
                if latest_failure.get("errors")
                else "Ingestion run failed"
            )

        status_val = latest_run.get("status") if latest_run else "idle"

        components[prefix] = ComponentIngestionHealth(
            component=prefix,
            title=title,
            api_key_configured=key_configured,
            status=status_val,
            last_run_at=latest_run.get("started_at") if latest_run else None,
            last_success_at=latest_success.get("started_at") if latest_success else None,
            last_error=last_err,
            contract_version=latest_run.get("contract_version") if latest_run else "1.0.0",
            records_accepted_total=totals.get("total_accepted", 0),
            records_rejected_total=totals.get("total_rejected", 0),
            records_processed_total=totals.get("total_processed", 0),
        )

    total_runs = await db[col.INGESTION_RUNS].count_documents({})
    active_runs = await db[col.INGESTION_RUNS].count_documents({"status": "running"})

    return AdminIngestionStatusResponse(
        components=components,
        total_runs=total_runs,
        active_runs=active_runs,
    )


@router.get(
    "/ingestion/runs",
    response_model=AdminPaginatedIngestionRunsResponse,
    summary="List Historical Ingestion Runs",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def list_admin_ingestion_runs(
    component: Optional[str] = Query(None, description="Filter by component (c1, c2, c3, c4)"),
    status: Optional[str] = Query(None, description="Filter by status (success, partial, failed)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedIngestionRunsResponse:
    query: Dict[str, Any] = {}
    if component:
        c_clean = component.strip().lower()
        query["component"] = {"$in": [c_clean, f"{c_clean}_affective", f"{c_clean}_trajectory", f"{c_clean}_risk", f"{c_clean}_intervention"]}
    if status:
        query["status"] = status.strip().lower()

    total = await db[col.INGESTION_RUNS].count_documents(query)
    skip = (page - 1) * page_size
    cursor = db[col.INGESTION_RUNS].find(query).sort("started_at", -1).skip(skip).limit(page_size)

    items: List[AdminIngestionRunItem] = []
    async for doc in cursor:
        items.append(
            AdminIngestionRunItem(
                id=str(doc.get("_id") or doc.get("id")),
                component=doc.get("component", ""),
                started_at=doc.get("started_at") or datetime.now(timezone.utc),
                finished_at=doc.get("finished_at"),
                status=doc.get("status", "unknown"),
                records_processed=doc.get("records_processed", 0),
                records_accepted=doc.get("records_accepted", 0),
                records_rejected=doc.get("records_rejected", 0),
                dry_run=doc.get("dry_run", False),
                contract_version=doc.get("contract_version"),
                error_message=doc.get("error_message"),
            )
        )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    return AdminPaginatedIngestionRunsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Phase 3: Privacy Governance & Controlled Reveal ──────────────────────────

@router.post(
    "/privacy/reveal",
    response_model=AdminIdentityRevealResponse,
    summary="Break-glass student identity reveal (Admin only)",
    description=(
        "Reveals student identity by PID. Strictly restricted to Admins. "
        "Auditors are rejected with 403. Requires >= 10 character justification reason. "
        "Audited as IDENTITY_REVEAL before returning. Identity is transient and never logged."
    ),
    dependencies=[Depends(get_current_admin)],
)
async def admin_breakglass_reveal(
    body: AdminIdentityRevealRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminIdentityRevealResponse:
    pid_clean = body.pid.strip()
    if not is_valid_pid(pid_clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PID format '{pid_clean}'. Expected STU_ followed by 8 hex characters.",
        )

    vault_record = await db[col.IDENTITY_VAULT].find_one({"pid": pid_clean})
    if not vault_record:
        vault_record = await db[col.IDENTITY_VAULT].find_one({"_id": pid_clean})

    if not vault_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pseudonym ID '{pid_clean}' was not found in the Identity Vault.",
        )

    admin_id = str(admin.id)
    admin_role = admin.role.value if hasattr(admin.role, "value") else str(admin.role)

    await log_event(
        request=request,
        db=db,
        action=AuditAction.IDENTITY_REVEAL,
        actor_id=admin_id,
        actor_role=admin_role,
        target_type="student",
        target_id=pid_clean,
        outcome=AuditOutcome.SUCCESS,
        reason=body.justification,
        details={
            "requester_role": admin_role,
            "reason_length": len(body.justification),
        },
    )

    return AdminIdentityRevealResponse(
        pid=vault_record["pid"],
        student_id=vault_record["student_id"],
        name=vault_record["name"],
        email=vault_record["email"],
    )


@router.get(
    "/privacy/reveal-history",
    response_model=AdminPaginatedRevealHistoryResponse,
    summary="List Identity Reveal Audit History",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def list_admin_reveal_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedRevealHistoryResponse:
    query = {"action": AuditAction.IDENTITY_REVEAL}
    total = await db[col.AUDIT_LOGS].count_documents(query)
    skip = (page - 1) * page_size
    cursor = db[col.AUDIT_LOGS].find(query).sort("timestamp", -1).skip(skip).limit(page_size)

    items: List[AdminRevealHistoryItem] = []
    async for doc in cursor:
        items.append(
            AdminRevealHistoryItem(
                id=str(doc.get("_id") or doc.get("id")),
                timestamp=doc.get("timestamp") or datetime.now(timezone.utc),
                actor_id=doc.get("actor_id", "unknown"),
                actor_role=doc.get("actor_role", "unknown"),
                pid=doc.get("target_id", "unknown"),
                reason=doc.get("reason", "No justification recorded"),
                outcome=doc.get("outcome", "success"),
            )
        )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    return AdminPaginatedRevealHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/privacy/scrub-test",
    response_model=AdminScrubTestResponse,
    summary="Interactive PII Scrubber Sandbox",
    description="Tests text redaction in-memory. Does not store or audit free text inputs.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def test_admin_pii_scrubber(
    body: AdminScrubTestRequest,
) -> AdminScrubTestResponse:
    clean_text, report = scrub_text(body.text, body.known_names)
    return AdminScrubTestResponse(
        clean_text=clean_text,
        redaction_report=report,
    )


# ── Phase 3: Exports Management & Audit History ───────────────────────────────

DATASET_COLLECTION_MAP: Dict[str, str] = {
    "c1_messages": col.MESSAGES,
    "c2_behavior": col.BEHAVIOR_WEEKLY,
    "c3_academic": getattr(col, "ACADEMIC_RECORDS", "grades"),
    "c3_affective": col.AFFECTIVE_WEEKLY,
    "c3_trajectories": col.ENGAGEMENT_TRAJECTORIES,
    "c4_risk": col.RISK_ASSESSMENTS,
    "c4_recommendations": col.RECOMMENDATIONS,
}


@router.get(
    "/exports/download",
    summary="Download Processed Dataset with Consent Filter and Formula Sanitization",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def download_admin_export(
    request: Request,
    dataset: str = Query(..., description="Dataset key (e.g. c1_messages, c2_behavior, c3_affective, c3_trajectories, c4_risk, c4_recommendations)"),
    course_id: Optional[str] = Query(None),
    week_index: Optional[int] = Query(None),
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    target_coll = DATASET_COLLECTION_MAP.get(dataset.lower().strip())
    if not target_coll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown dataset '{dataset}'. Supported datasets: {list(DATASET_COLLECTION_MAP.keys())}",
        )

    # 1. Strictly exclude withdrawn students via active consent notice
    eligible_pids = await get_eligible_consenting_pids(db)

    # 2. Build collection query
    query: Dict[str, Any] = {}
    if eligible_pids:
        query["$or"] = [{"source": "oulad"}, {"pid": {"$in": list(eligible_pids)}}]
    else:
        query["source"] = "oulad"

    if course_id:
        query["course_id"] = course_id.strip()
    if week_index is not None:
        query["week_index"] = week_index

    # 3. Retrieve documents (exclude _id)
    cursor = db[target_coll].find(query, {"_id": 0}).limit(5000)
    records = await cursor.to_list(length=5000)

    # 4. Feature 7 Audit Log: EXPORT_GENERATED before returning data
    user_id = str(current_user.id)
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=user_id,
        actor_role=user_role,
        target_type="export",
        target_id=dataset,
        outcome=AuditOutcome.SUCCESS,
        details={
            "dataset": dataset,
            "format": format,
            "row_count": len(records),
            "course_id": course_id,
            "week_index": week_index,
        },
    )

    filename = f"export_{dataset}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    if format == "json":
        return JSONResponse(
            content={"dataset": dataset, "count": len(records), "records": records},
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    # Format CSV with formula sanitization
    output = io.StringIO()
    if records:
        fieldnames = list(records[0].keys())
        writer = csv.writer(output)
        writer.writerow(fieldnames)
        for r in records:
            row = []
            for f in fieldnames:
                val = r.get(f)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                elif val is None:
                    val = ""
                row.append(_sanitize_csv_cell(str(val)))
            writer.writerow(row)
    else:
        writer = csv.writer(output)
        writer.writerow(["message"])
        writer.writerow(["No matching records found for export."])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@router.get(
    "/exports/history",
    response_model=AdminPaginatedExportHistoryResponse,
    summary="List Data Export Audit History",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def list_admin_export_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminPaginatedExportHistoryResponse:
    query = {"action": AuditAction.EXPORT_GENERATED}
    total = await db[col.AUDIT_LOGS].count_documents(query)
    skip = (page - 1) * page_size
    cursor = db[col.AUDIT_LOGS].find(query).sort("timestamp", -1).skip(skip).limit(page_size)

    items: List[AdminExportHistoryItem] = []
    async for doc in cursor:
        dtls = doc.get("details") or {}
        items.append(
            AdminExportHistoryItem(
                id=str(doc.get("_id") or doc.get("id")),
                timestamp=doc.get("timestamp") or datetime.now(timezone.utc),
                actor_id=doc.get("actor_id", "unknown"),
                actor_role=doc.get("actor_role", "unknown"),
                dataset=dtls.get("dataset", doc.get("target_id", "dataset")),
                format=dtls.get("format", "csv"),
                row_count=dtls.get("row_count", 0),
                filters={
                    k: v for k, v in dtls.items()
                    if k in ("course_id", "week_index", "format") and v is not None
                },
            )
        )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    return AdminPaginatedExportHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Phase 3: System Diagnostics & Health ─────────────────────────────────────

@router.get(
    "/system/health",
    response_model=AdminSystemHealthResponse,
    summary="Get System Health, Latency, Migrations, and OULAD Status",
    description="Returns platform health, DB latency, applied migrations, contract version, and OULAD status. Never exposes secrets.",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))],
)
async def get_admin_system_health(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminSystemHealthResponse:
    ping_start = time.perf_counter()
    db_status = "connected"
    try:
        await db.command("ping")
        ping_ms = round((time.perf_counter() - ping_start) * 1000, 2)
    except Exception as exc:
        db_status = f"unhealthy: {exc}"
        ping_ms = -1.0

    migrations_cursor = db[col.SCHEMA_MIGRATIONS].find({}).sort("applied_at", -1)
    applied_migrations: List[AdminMigrationItem] = []
    async for m in migrations_cursor:
        applied_migrations.append(
            AdminMigrationItem(
                migration_id=str(m.get("_id") or m.get("migration_id")),
                applied_at=m.get("applied_at") or datetime.now(timezone.utc),
            )
        )

    contract_schemas = [
        "AffectiveWeeklyVector",
        "EngagementTrajectory",
        "RiskAssessment",
        "InterventionRecommendation",
        "TextMessageRecord",
        "BehaviorWeeklyRecord",
        "AcademicRecord",
        "InterventionOutcome",
    ]

    oulad_vault_count = await db[col.IDENTITY_VAULT].count_documents(
        {"$or": [{"is_imported": True}, {"source": "oulad"}]}
    )
    oulad_course_count = await db[col.COURSES].count_documents({"source": "oulad"})
    oulad_enrol_count = await db[col.ENROLMENTS].count_documents({"source": "oulad"})

    oulad_status = {
        "is_imported": oulad_vault_count > 0,
        "imported_students": oulad_vault_count,
        "imported_courses": oulad_course_count,
        "imported_enrolments": oulad_enrol_count,
        "cli_command": "python -m app.importers.oulad.cli --data-dir <path-to-oulad-csvs>",
    }

    return AdminSystemHealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        db_status=db_status,
        db_ping_ms=ping_ms,
        contract_version=CONTRACT_VERSION,
        contract_schemas=contract_schemas,
        applied_migrations=applied_migrations,
        total_migrations_applied=len(applied_migrations),
        oulad_status=oulad_status,
    )


