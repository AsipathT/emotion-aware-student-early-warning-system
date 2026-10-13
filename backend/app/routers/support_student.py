"""
backend/app/routers/support_student.py

Feature 38-A: Student Support Hub & Uptake Response Router (Component 4 Uptake Metric).
Allows students to view their own offered and active support interventions with friendly,
non-stigmatizing labels, and record voluntary uptake responses (accept / decline).
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.db import collections as col
from app.db.storage_models import Decision, InterventionOutcomeStorage
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.support_resource import COL_SUPPORT_RESOURCES
from app.models.user import User, UserRole
from app.schemas.support_student import (
    MarkResourceViewedResponse,
    StudentSharedResourceItem,
    StudentSupportInterventionItem,
    StudentSupportListResponse,
    StudentSupportResponseRequest,
    StudentSupportResponseResult,
)
from app.services.intervention_catalog import get_entry
from app.services.intervention_service import change_status
from app.services.notification_service import create_notification

logger = logging.getLogger("app.support_student")

router = APIRouter(
    prefix="/api/v1/support/me",
    tags=["Student Support"],
)


def _require_student(user: User) -> None:
    """Enforces that the active user is a student."""
    role_str = str(user.role.value if hasattr(user.role, "value") else user.role).strip().lower()
    if role_str != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Student role required for student support workspace.",
        )


async def _resolve_student_pid(user: User, db: AsyncIOMotorDatabase) -> Optional[str]:
    """Resolves student user's pseudonymized identifier."""
    if user.pid:
        return str(user.pid).strip()
    user_doc = await db.users.find_one({"_id": str(user.id)})
    if not user_doc:
        user_doc = await db.users.find_one({"id": str(user.id)})
    if user_doc and user_doc.get("pid"):
        return str(user_doc["pid"]).strip()
    return None


@router.get(
    "/interventions",
    response_model=StudentSupportListResponse,
    summary="Get student's own support interventions",
)
async def get_my_support_interventions(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Retrieves the authenticated student's own support interventions.
    Excludes all predictive analytics, scores, risk tiers, and clinical notes.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)

    if not student_pid:
        return StudentSupportListResponse(items=[], total_count=0)

    # Allowed student-visible lifecycle states
    allowed_statuses = ["offered", "accepted", "in_progress", "completed", "declined"]
    cursor = db[COL_INTERVENTION_RECORDS].find({
        "pid": student_pid,
        "status": {"$in": allowed_statuses},
    }).sort("created_at", -1)

    docs = await cursor.to_list(length=100)

    # Collect all resource IDs across interventions to resolve in batch
    all_res_ids = []
    for d in docs:
        for sr in d.get("shared_resources", []):
            rid = str(sr.get("resource_id", "")).strip()
            if rid:
                all_res_ids.append(rid)

    res_map = {}
    if all_res_ids:
        res_cursor = db[COL_SUPPORT_RESOURCES].find({
            "$or": [{"id": {"$in": all_res_ids}}, {"_id": {"$in": all_res_ids}}],
        })
        async for r in res_cursor:
            key = str(r.get("id") or r.get("_id"))
            res_map[key] = r

    items = []
    for doc in docs:
        itype = doc.get("intervention_type")
        catalog_entry = get_entry(itype)

        student_label = doc.get("student_label") or catalog_entry.get("student_label") or "Academic Guidance & Support"
        friendly_description = catalog_entry.get("description") or "Guidance and learning support prepared for your courses."
        delivery_mod = catalog_entry.get("delivery_module") or "none"

        # Determine offered_at from status history
        offered_at = None
        for sh in doc.get("status_history", []):
            if sh.get("status") == "offered" or sh.get("to_status") == "offered":
                offered_at = sh.get("at") or sh.get("changed_at")
                break
        if not offered_at:
            offered_at = doc.get("updated_at") or doc.get("created_at")

        # Resolve shared resources for this intervention (Feature 38-C)
        resources_list = []
        for sr in doc.get("shared_resources", []):
            rid = str(sr.get("resource_id", "")).strip()
            meta = res_map.get(rid) or {}
            resources_list.append({
                "id": rid,
                "resource_id": rid,
                "title": meta.get("title") or "Recommended Resource",
                "description": meta.get("description") or "",
                "resource_type": meta.get("resource_type") or "resource",
                "type": meta.get("resource_type") or "resource",
                "url": meta.get("url"),
                "contact_info": meta.get("contact_info"),
                "message": sr.get("message"),
                "shared_at": sr.get("shared_at"),
                "viewed": bool(sr.get("viewed_at")),
                "viewed_at": sr.get("viewed_at"),
            })

        items.append(
            StudentSupportInterventionItem(
                id=doc["id"],
                student_label=student_label,
                description=friendly_description,
                status=doc["status"],
                delivery_module=delivery_mod,
                scheduled_for=doc.get("scheduled_for"),
                offered_at=offered_at,
                assigned_staff_name=doc.get("assigned_staff_name"),
                student_response=doc.get("student_response"),
                slot=None,
                resources=resources_list if resources_list else None,
                mentor=None,
            )
        )

    return StudentSupportListResponse(
        items=items,
        total_count=len(items),
    )


@router.post(
    "/interventions/{intervention_id}/respond",
    response_model=StudentSupportResponseResult,
    summary="Respond to offered intervention (Accept / Decline)",
)
async def respond_to_support_intervention(
    intervention_id: str,
    payload: StudentSupportResponseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Records student acceptance or decline of an offered support intervention.
    Enforces that the intervention belongs to the student and is currently in 'offered' status.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)

    if not student_pid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    clean_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({
        "$or": [{"id": clean_id}, {"_id": clean_id}]
    })

    if not rec or rec.get("pid") != student_pid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intervention record not found.",
        )

    current_status = str(rec.get("status", "")).strip().lower()
    if current_status != "offered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intervention cannot be responded to in state '{current_status}'. Only 'offered' interventions can be accepted or declined.",
        )

    now_utc = datetime.now(timezone.utc)
    target_status = "accepted" if payload.response == "accept" else "declined"
    reason_str = payload.decline_reason.value if payload.decline_reason else None

    student_response_data = {
        "response": payload.response,
        "reason": reason_str,
        "at": now_utc,
    }

    # Update student_response field in intervention_records
    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {"$set": {"student_response": student_response_data}},
    )

    # Perform validated lifecycle transition via change_status
    note_text = f"Student response: {payload.response}"
    if reason_str:
        note_text += f" (reason: {reason_str})"

    await change_status(
        db=db,
        record=rec,
        new_status=target_status,
        actor_id=str(current_user.id),
        note=note_text,
    )

    # If declined and intervention originated from a recommendation:
    # Upsert canonical intervention_outcomes (completed=False, observed_change="declined by student")
    if target_status == "declined" and rec.get("recommendation_id"):
        rec_id = str(rec["recommendation_id"]).strip()
        existing_outcome = await db[col.INTERVENTION_OUTCOMES].find_one({"recommendation_id": rec_id})
        outcome_id = (
            str(existing_outcome["_id"])
            if existing_outcome and "_id" in existing_outcome
            else str(uuid.uuid4())
        )
        dec_val = existing_outcome.get("decision", "approved") if existing_outcome else "approved"
        notes_present_val = existing_outcome.get("notes_present", False) if existing_outcome else False

        canonical_outcome = InterventionOutcomeStorage(
            id=outcome_id,
            recommendation_id=rec_id,
            decision=Decision(dec_val),
            completed=False,
            observed_change="declined by student",
            notes_present=notes_present_val,
        )
        await db[col.INTERVENTION_OUTCOMES].replace_one(
            {"recommendation_id": rec_id},
            canonical_outcome.model_dump(by_alias=True),
            upsert=True,
        )

    # Notify assigned counsellor of student response (supportive, neutral copy)
    counsellor_id = rec.get("assigned_to") or rec.get("created_by")
    if counsellor_id:
        catalog_entry = get_entry(rec.get("intervention_type"))
        friendly_label = catalog_entry.get("student_label") or "Support Consultation"
        if target_status == "declined":
            notif_title = "Student Support Response"
            notif_body = f"A student has declined the offered support ({friendly_label})."
        else:
            notif_title = "Student Accepted Support"
            notif_body = f"A student has accepted the offered support ({friendly_label})."

        await create_notification(
            db=db,
            user_id=counsellor_id,
            type="support_response",
            title=notif_title,
            body=notif_body,
            link=f"/staff/interventions/{clean_id}",
            related_id=clean_id,
        )

    response_message = (
        "Support option accepted. Your advisor has been notified."
        if payload.response == "accept"
        else "Support option declined."
    )

    return StudentSupportResponseResult(
        id=clean_id,
        status=target_status,
        student_response=student_response_data,
        message=response_message,
    )


@router.post(
    "/interventions/{id}/resources/{rid}/viewed",
    response_model=MarkResourceViewedResponse,
    summary="Mark shared resource as viewed by student",
    description="Records student engagement uptake when opening or reading a shared resource or referral. Sets viewed_at once.",
)
async def mark_shared_resource_viewed(
    id: str,
    rid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MarkResourceViewedResponse:
    """
    Sets viewed_at timestamp once on the shared_resources entry for this student's intervention.
    Enforces that the intervention belongs strictly to the authenticated student.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)
    if not student_pid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    clean_id = str(id).strip()
    clean_rid = str(rid).strip()

    rec = await db[COL_INTERVENTION_RECORDS].find_one({
        "$or": [{"id": clean_id}, {"_id": clean_id}],
    })

    if not rec or rec.get("pid") != student_pid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intervention record not found.",
        )

    shared_resources = rec.get("shared_resources") or []
    target_entry = None
    for entry in shared_resources:
        if str(entry.get("resource_id")) == clean_rid:
            target_entry = entry
            break

    if not target_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared resource not found on this intervention.",
        )

    viewed_time = target_entry.get("viewed_at")
    if not viewed_time:
        now_utc = datetime.now(timezone.utc)
        viewed_time = now_utc
        await db[COL_INTERVENTION_RECORDS].update_one(
            {
                "$or": [{"id": clean_id}, {"_id": clean_id}],
                "pid": student_pid,
                "shared_resources.resource_id": clean_rid,
            },
            {
                "$set": {"shared_resources.$.viewed_at": now_utc},
            },
        )

    return MarkResourceViewedResponse(
        success=True,
        resource_id=clean_rid,
        viewed_at=viewed_time,
    )

