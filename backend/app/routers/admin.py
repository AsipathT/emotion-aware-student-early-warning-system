"""
backend/app/routers/admin.py

Admin Panel endpoints (MongoDB backed - Feature 40).
Provides platform governance, overview KPIs, and user management.
"""

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_admin, require_roles
from app.core.privacy import is_valid_pid, pseudonymize
from app.core.security import hash_password
from app.db import collections as col
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminConsentSummary,
    AdminEnrolmentSummary,
    AdminOverviewResponse,
    AdminPaginatedUsersResponse,
    AdminUserCreateRequest,
    AdminUserDetailResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
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
    total_students = users_by_role.get("student", 0)
    accepted_consent = await db[col.CONSENT_RECORDS].count_documents({"status": "accepted"})
    declined_consent = await db[col.CONSENT_RECORDS].count_documents({"status": "declined"})
    withdrawn_consent = await db[col.CONSENT_RECORDS].count_documents({"status": "withdrawn"})
    pending_consent = max(0, total_students - (accepted_consent + declined_consent + withdrawn_consent))
    coverage_pct = round((accepted_consent / total_students * 100.0), 1) if total_students > 0 else 100.0

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
