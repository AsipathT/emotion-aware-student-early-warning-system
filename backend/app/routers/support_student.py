"""
backend/app/routers/support_student.py

Feature 38-A: Student Support Hub & Uptake Response Router (Component 4 Uptake Metric).
Allows students to view their own offered and active support interventions with friendly,
non-stigmatizing labels, and record voluntary uptake responses (accept / decline).
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.db import collections as col
from app.db.storage_models import Decision, InterventionOutcomeStorage
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.support_resource import COL_SUPPORT_RESOURCES
from app.models.support_slot import COL_COUNSELLING_SLOTS
from app.models.support_mentoring import COL_MENTORING_ASSIGNMENTS
from app.models.user import User, UserRole
from app.schemas.staff_slots import SlotBookRequest
from app.schemas.support_student import (
    AvailableSlotItem,
    AvailableSlotListResponse,
    BookedSlotItem,
    MarkResourceViewedResponse,
    MentorAssignmentItem,
    MentorAssignmentListResponse,
    SlotBookingResult,
    SlotCancelResult,
    StudentSharedResourceItem,
    StudentSupportInterventionItem,
    StudentSupportListResponse,
    StudentSupportResponseRequest,
    StudentSupportResponseResult,
)
from app.services.intervention_catalog import get_entry
from app.services.intervention_service import change_status
from app.services.notification_service import create_notification, notify_pid


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

    # Collect intervention IDs to look up booked counselling slots (Feature 38-B)
    interv_ids = [str(d.get("id") or d.get("_id")) for d in docs]
    booked_slots_map = {}
    if interv_ids:
        b_cursor = db[COL_COUNSELLING_SLOTS].find({
            "intervention_id": {"$in": interv_ids},
            "booked_by_user_id": str(current_user.id),
            "cancelled_at": None,
        })
        async for bs in b_cursor:
            key = str(bs.get("intervention_id"))
            booked_slots_map[key] = bs

    # Resolve counsellor names for booked slots
    counsellor_ids = list({str(s.get("counsellor_id")) for s in booked_slots_map.values() if s.get("counsellor_id")})
    counsellor_names = {}
    if counsellor_ids:
        u_cursor = db.users.find({"$or": [{"_id": {"$in": counsellor_ids}}, {"id": {"$in": counsellor_ids}}]})
        async for u in u_cursor:
            uid = str(u.get("_id") or u.get("id"))
            counsellor_names[uid] = u.get("full_name") or u.get("name") or "Academic Counsellor"

    # Collect intervention IDs to look up active peer mentoring assignments (Feature 38-D)
    active_mentors_map = {}
    if interv_ids:
        m_cursor = db[COL_MENTORING_ASSIGNMENTS].find({
            "intervention_id": {"$in": interv_ids},
            "status": "active",
        })
        async for ma in m_cursor:
            key = str(ma.get("intervention_id"))
            active_mentors_map[key] = ma

    # Resolve mentor names for active assignments
    mentor_ids = list({str(m.get("mentor_user_id")) for m in active_mentors_map.values() if m.get("mentor_user_id")})
    mentor_names = {}
    if mentor_ids:
        mu_cursor = db.users.find({"$or": [{"_id": {"$in": mentor_ids}}, {"id": {"$in": mentor_ids}}]})
        async for mu in mu_cursor:
            muid = str(mu.get("_id") or mu.get("id"))
            mentor_names[muid] = mu.get("full_name") or mu.get("name") or "Peer Mentor"

    items = []
    for doc in docs:
        doc_id = str(doc.get("id") or doc.get("_id"))
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

        # Resolve booked appointment slot (Feature 38-B)
        booked_slot_doc = booked_slots_map.get(doc_id)
        slot_data = None
        if booked_slot_doc:
            cid = str(booked_slot_doc.get("counsellor_id", ""))
            slot_data = {
                "id": str(booked_slot_doc.get("id") or booked_slot_doc.get("_id")),
                "counsellor_id": cid,
                "counsellor_name": counsellor_names.get(cid) or "Academic Counsellor",
                "start_at": booked_slot_doc.get("start_at"),
                "duration_minutes": int(booked_slot_doc.get("duration_minutes", 45)),
                "mode": booked_slot_doc.get("mode", "online"),
                "location_or_link": booked_slot_doc.get("location_or_link"),
                "booked_at": booked_slot_doc.get("booked_at"),
            }

        # Resolve active peer mentor (Feature 38-D)
        active_m = active_mentors_map.get(doc_id)
        mentor_data = None
        if active_m:
            mid = str(active_m.get("mentor_user_id", ""))
            mentor_data = {
                "id": str(active_m.get("id") or active_m.get("_id")),
                "mentor_user_id": mid,
                "full_name": mentor_names.get(mid) or "Peer Mentor",
                "status": active_m.get("status", "active"),
                "since": active_m.get("created_at"),
            }

        items.append(
            StudentSupportInterventionItem(
                id=doc_id,
                student_label=student_label,
                description=friendly_description,
                status=doc["status"],
                delivery_module=delivery_mod,
                scheduled_for=doc.get("scheduled_for"),
                offered_at=offered_at,
                assigned_staff_name=doc.get("assigned_staff_name"),
                student_response=doc.get("student_response"),
                slot=slot_data,
                resources=resources_list if resources_list else None,
                mentor=mentor_data,
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


@router.get(
    "/slots",
    response_model=AvailableSlotListResponse,
    summary="Get open available counselling slots",
    description="Retrieves open upcoming appointment slots starting at least 2 hours in the future. Location and link are masked for privacy.",
)
async def get_available_counselling_slots(
    intervention_id: str = Query(..., description="ID of student's counselling intervention"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AvailableSlotListResponse:
    """
    Returns open future slots (start_at > now + 2h, booked_by None) for the assigned counsellor
    (or any counsellor if none is assigned), with location/link strictly excluded.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)
    if not student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    clean_interv_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({"$or": [{"id": clean_interv_id}, {"_id": clean_interv_id}]})
    if not rec or rec.get("pid") != student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention record not found.")

    # Validate delivery module
    catalog_entry = get_entry(rec.get("intervention_type"))
    if catalog_entry.get("delivery_module") != "counselling_booking":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intervention delivery module is not counselling_booking.",
        )

    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc + timedelta(hours=2)

    query: dict = {
        "booked_by_user_id": None,
        "cancelled_at": None,
        "start_at": {"$gt": cutoff_time},
    }

    # If intervention has an assigned counsellor, filter by that counsellor
    assigned_to = rec.get("assigned_to")
    if assigned_to:
        query["counsellor_id"] = str(assigned_to)

    cursor = db[COL_COUNSELLING_SLOTS].find(query).sort("start_at", 1)
    slots_list = await cursor.to_list(length=100)

    # Resolve counsellor names
    c_ids = list({str(s.get("counsellor_id")) for s in slots_list if s.get("counsellor_id")})
    name_map = {}
    if c_ids:
        u_cursor = db.users.find({"$or": [{"_id": {"$in": c_ids}}, {"id": {"$in": c_ids}}]})
        async for u in u_cursor:
            uid = str(u.get("_id") or u.get("id"))
            name_map[uid] = u.get("full_name") or u.get("name") or "Academic Counsellor"

    items: List[AvailableSlotItem] = []
    for s in slots_list:
        cid = str(s.get("counsellor_id", ""))
        items.append(
            AvailableSlotItem(
                id=str(s.get("id") or s.get("_id")),
                counsellor_id=cid,
                counsellor_name=name_map.get(cid) or "Academic Counsellor",
                start_at=s.get("start_at"),
                duration_minutes=int(s.get("duration_minutes", 45)),
                mode=s.get("mode", "online"),
            )
        )

    return AvailableSlotListResponse(items=items, total_count=len(items))


@router.post(
    "/interventions/{id}/book",
    response_model=SlotBookingResult,
    summary="Book a counselling slot for an intervention",
    description="Atomically books an open slot for an accepted or in-progress counselling intervention. Sets intervention schedule and transitions status.",
)
async def book_counselling_slot(
    id: str,
    payload: SlotBookRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SlotBookingResult:
    """
    Atomically books a counselling slot for an accepted/in_progress intervention.
    Enforces atomic find_one_and_update to guarantee zero double-bookings.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)
    if not student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    clean_id = str(id).strip()
    clean_slot_id = str(payload.slot_id).strip()

    rec = await db[COL_INTERVENTION_RECORDS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not rec or rec.get("pid") != student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention record not found.")

    # Status check: only accepted or in_progress allowed
    current_status = str(rec.get("status", "")).strip().lower()
    if current_status not in ("accepted", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointments can only be booked for 'accepted' or 'in_progress' interventions (current status: '{current_status}').",
        )

    # Delivery module check
    catalog_entry = get_entry(rec.get("intervention_type"))
    if catalog_entry.get("delivery_module") != "counselling_booking":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This intervention does not use the counselling booking delivery module.",
        )

    # Check for active existing booking on this intervention
    existing_booking = await db[COL_COUNSELLING_SLOTS].find_one({
        "intervention_id": clean_id,
        "booked_by_user_id": str(current_user.id),
        "cancelled_at": None,
    })
    if existing_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active appointment booked for this intervention.",
        )

    # ATOMIC find_one_and_update
    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc + timedelta(hours=2)

    updated_slot = await db[COL_COUNSELLING_SLOTS].find_one_and_update(
        {
            "$or": [{"id": clean_slot_id}, {"_id": clean_slot_id}],
            "booked_by_user_id": None,
            "cancelled_at": None,
            "start_at": {"$gt": cutoff_time},
        },
        {
            "$set": {
                "booked_by_user_id": str(current_user.id),
                "intervention_id": clean_id,
                "booked_at": now_utc,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated_slot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is no longer available or starts within 2 hours.",
        )

    slot_start = updated_slot["start_at"]
    target_status = current_status

    # Lifecycle state transition: if currently accepted, advance to in_progress
    if current_status == "accepted":
        try:
            await change_status(
                db=db,
                record=rec,
                new_status="in_progress",
                actor_id=str(current_user.id),
                note="Student confirmed counselling appointment",
            )
            target_status = "in_progress"
        except Exception as exc:
            logger.warning("Status transition on booking failed: %s", exc)

    # Set scheduled_for on intervention_records
    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {"$set": {"scheduled_for": slot_start, "updated_at": now_utc}},
    )

    # Resolve counsellor name
    cid = str(updated_slot.get("counsellor_id", ""))
    counsellor_doc = await db.users.find_one({"$or": [{"_id": cid}, {"id": cid}]})
    counsellor_name = (
        (counsellor_doc.get("full_name") or counsellor_doc.get("name"))
        if counsellor_doc
        else "Academic Counsellor"
    )

    formatted_time = (
        slot_start.strftime("%A, %B %d at %I:%M %p UTC")
        if isinstance(slot_start, datetime)
        else str(slot_start)
    )

    # Notify student (appointment_confirmed template)
    try:
        await notify_pid(
            db=db,
            pid=student_pid,
            template_key="appointment_confirmed",
            scheduled_time=formatted_time,
            link="/support",
            related_id=clean_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify student of appointment confirmation: %s", exc)

    # Notify counsellor (neutral)
    try:
        await create_notification(
            db=db,
            user_id=cid,
            type="appointment_confirmed",
            title="Counselling Appointment Booked",
            body=f"A student has booked a confidential consultation session for {formatted_time}.",
            link=f"/staff/interventions/{clean_id}",
            related_id=clean_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify counsellor of appointment booking: %s", exc)

    booked_item = BookedSlotItem(
        id=str(updated_slot.get("id") or updated_slot.get("_id")),
        counsellor_id=cid,
        counsellor_name=counsellor_name,
        start_at=slot_start,
        duration_minutes=int(updated_slot.get("duration_minutes", 45)),
        mode=updated_slot.get("mode", "online"),
        location_or_link=updated_slot.get("location_or_link"),
        booked_at=now_utc,
    )

    return SlotBookingResult(
        success=True,
        slot=booked_item,
        intervention_id=clean_id,
        status=target_status,
        message=f"Appointment booked successfully for {formatted_time}.",
    )


@router.post(
    "/interventions/{id}/cancel-booking",
    response_model=SlotCancelResult,
    summary="Cancel booked appointment (Student)",
    description="Frees a booked slot if cancelled at least 2 hours in advance. Clears intervention schedule and notifies the counsellor.",
)
async def cancel_counselling_booking_by_student(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SlotCancelResult:
    """
    Frees a student's booked appointment slot. Enforces the 2-hour advance cancellation rule.
    """
    _require_student(current_user)
    student_pid = await _resolve_student_pid(current_user, db)
    if not student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    clean_id = str(id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not rec or rec.get("pid") != student_pid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention record not found.")

    # Find the active booked slot
    slot = await db[COL_COUNSELLING_SLOTS].find_one({
        "intervention_id": clean_id,
        "booked_by_user_id": str(current_user.id),
        "cancelled_at": None,
    })
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active appointment booking found for this intervention.",
        )

    # 2-hour cancellation rule
    now_utc = datetime.now(timezone.utc)
    slot_start = slot.get("start_at")
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=timezone.utc)

    if slot_start <= now_utc + timedelta(hours=2):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointments can only be cancelled at least 2 hours prior to the scheduled time.",
        )

    # Free the slot
    slot_id = slot.get("id") or slot.get("_id")
    await db[COL_COUNSELLING_SLOTS].update_one(
        {"$or": [{"id": slot_id}, {"_id": slot_id}]},
        {
            "$set": {
                "booked_by_user_id": None,
                "intervention_id": None,
                "booked_at": None,
            }
        },
    )

    # Clear intervention schedule
    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {"$set": {"scheduled_for": None, "updated_at": now_utc}},
    )

    # Notify counsellor
    try:
        formatted_time = slot_start.strftime("%A, %B %d at %I:%M %p UTC")
        cid = str(slot.get("counsellor_id", ""))
        await create_notification(
            db=db,
            user_id=cid,
            type="appointment_cancelled",
            title="Appointment Cancelled by Student",
            body=f"A student cancelled their scheduled counselling consultation for {formatted_time}.",
            link=f"/staff/interventions/{clean_id}",
            related_id=clean_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify counsellor of student appointment cancellation: %s", exc)

    return SlotCancelResult(
        success=True,
        message="Appointment cancelled successfully. The slot has been released.",
    )


@router.get(
    "/mentoring",
    response_model=MentorAssignmentListResponse,
    summary="Get my peer mentor assignments (Mentor view)",
    description="Retrieves active and concluded mentoring connections where the authenticated student serves as the peer mentor. Contains zero intervention analytics or deficit indicators.",
)
async def get_my_mentoring_assignments(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MentorAssignmentListResponse:
    """
    Returns peer mentoring assignments where the current student is the mentor.
    Mentors see ONLY the mentee display name, status, and pairing timestamp.
    STRICT PRIVACY: Zero intervention details, type labels, or risk scores reach the mentor.
    """
    _require_student(current_user)
    uid = str(current_user.id)

    cursor = db[COL_MENTORING_ASSIGNMENTS].find({
        "mentor_user_id": uid
    }).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    # Resolve mentee display names
    mentee_ids = list({str(d.get("mentee_user_id")) for d in docs if d.get("mentee_user_id")})
    name_map = {}
    if mentee_ids:
        u_cursor = db.users.find({"$or": [{"_id": {"$in": mentee_ids}}, {"id": {"$in": mentee_ids}}]})
        async for u in u_cursor:
            m_id = str(u.get("_id") or u.get("id"))
            name_map[m_id] = u.get("full_name") or u.get("name") or "Student"

    items: List[MentorAssignmentItem] = []
    for d in docs:
        mid = str(d.get("mentee_user_id", ""))
        items.append(
            MentorAssignmentItem(
                id=str(d.get("id") or d.get("_id")),
                mentee_user_id=mid,
                mentee_display_name=name_map.get(mid) or "Student",
                status=d.get("status", "active"),
                since=d["created_at"],
                ended_at=d.get("ended_at"),
            )
        )

    return MentorAssignmentListResponse(items=items, total_count=len(items))



