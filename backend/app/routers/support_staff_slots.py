"""
backend/app/routers/support_staff_slots.py

Feature 38-B: Staff Counselling Slot Publishing & Management Router.
Prefix: /api/v1/support/slots
Allows counsellors and administrators to:
  1. Publish appointment slots in advance (with overlap detection and future-time constraints).
  2. List their own upcoming slots with booking and status metadata.
  3. Delete open/unbooked slots.
  4. Cancel booked appointments with automatic student notification and schedule unsynchronization.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.support_slot import COL_COUNSELLING_SLOTS
from app.models.user import User
from app.schemas.staff_slots import (
    SlotCreateRequest,
    SlotListResponse,
    SlotResponse,
)
from app.services.notification_service import create_notification
from app.services.staff_access import require_staff

logger = logging.getLogger("app.support_staff_slots")

router = APIRouter(
    prefix="/api/v1/support/slots",
    tags=["Support Slots"],
)


@router.post(
    "",
    response_model=SlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish counselling appointment slot",
    description="Publishes a future appointment slot for students to book. Rejects overlapping slots for the same counsellor.",
)
async def create_counselling_slot(
    payload: SlotCreateRequest,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SlotResponse:
    now_utc = datetime.now(timezone.utc)
    start_utc = payload.start_at
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)

    if start_utc <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Slot start time must be in the future.",
        )

    end_utc = start_utc + timedelta(minutes=payload.duration_minutes)
    counsellor_id_str = str(current_user.id)

    # Overlap detection for the same counsellor:
    # Query all uncancelled slots that could potentially intersect
    window_start = start_utc - timedelta(hours=3)
    existing_cursor = db[COL_COUNSELLING_SLOTS].find({
        "counsellor_id": counsellor_id_str,
        "cancelled_at": None,
        "start_at": {"$gte": window_start, "$lte": end_utc},
    })

    async for existing in existing_cursor:
        ex_start = existing["start_at"]
        if ex_start.tzinfo is None:
            ex_start = ex_start.replace(tzinfo=timezone.utc)
        ex_duration = int(existing.get("duration_minutes", 45))
        ex_end = ex_start + timedelta(minutes=ex_duration)

        # Overlap interval condition: max(start1, start2) < min(end1, end2)
        if max(start_utc, ex_start) < min(end_utc, ex_end):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Slot overlaps with an existing appointment slot "
                    f"({ex_start.strftime('%Y-%m-%d %H:%M UTC')} - {ex_end.strftime('%H:%M UTC')})."
                ),
            )

    slot_id = str(uuid.uuid4())
    doc = {
        "_id": slot_id,
        "id": slot_id,
        "counsellor_id": counsellor_id_str,
        "start_at": start_utc,
        "duration_minutes": payload.duration_minutes,
        "mode": payload.mode,
        "location_or_link": payload.location_or_link.strip(),
        "booked_by_user_id": None,
        "intervention_id": None,
        "booked_at": None,
        "cancelled_at": None,
        "created_at": now_utc,
    }

    await db[COL_COUNSELLING_SLOTS].insert_one(doc)

    counsellor_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None)

    return SlotResponse(
        id=slot_id,
        counsellor_id=counsellor_id_str,
        counsellor_name=counsellor_name,
        start_at=doc["start_at"],
        duration_minutes=doc["duration_minutes"],
        mode=doc["mode"],
        location_or_link=doc["location_or_link"],
        is_booked=False,
        booked_by_user_id=None,
        intervention_id=None,
        booked_at=None,
        cancelled_at=None,
        created_at=doc["created_at"],
    )


@router.get(
    "/mine",
    response_model=SlotListResponse,
    summary="List counsellor's own slots",
    description="Retrieves appointment slots published by the authenticated counsellor with optional date range filters.",
)
async def list_my_counselling_slots(
    from_date: Optional[datetime] = Query(default=None, alias="from", description="Filter slots starting after this UTC time"),
    to_date: Optional[datetime] = Query(default=None, alias="to", description="Filter slots starting before this UTC time"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SlotListResponse:
    counsellor_id_str = str(current_user.id)
    query: dict = {"counsellor_id": counsellor_id_str}

    date_filters = {}
    if from_date is not None:
        if from_date.tzinfo is None:
            from_date = from_date.replace(tzinfo=timezone.utc)
        date_filters["$gte"] = from_date

    if to_date is not None:
        if to_date.tzinfo is None:
            to_date = to_date.replace(tzinfo=timezone.utc)
        date_filters["$lte"] = to_date

    if date_filters:
        query["start_at"] = date_filters

    cursor = db[COL_COUNSELLING_SLOTS].find(query).sort("start_at", 1)

    counsellor_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None)

    items: List[SlotResponse] = []
    async for doc in cursor:
        sid = str(doc.get("id") or doc.get("_id"))
        is_booked = bool(doc.get("booked_by_user_id")) and doc.get("cancelled_at") is None
        items.append(
            SlotResponse(
                id=sid,
                counsellor_id=str(doc.get("counsellor_id", "")),
                counsellor_name=counsellor_name,
                start_at=doc.get("start_at", datetime.now(timezone.utc)),
                duration_minutes=int(doc.get("duration_minutes", 45)),
                mode=doc.get("mode", "online"),
                location_or_link=doc.get("location_or_link"),
                is_booked=is_booked,
                booked_by_user_id=doc.get("booked_by_user_id"),
                intervention_id=doc.get("intervention_id"),
                booked_at=doc.get("booked_at"),
                cancelled_at=doc.get("cancelled_at"),
                created_at=doc.get("created_at", datetime.now(timezone.utc)),
            )
        )

    return SlotListResponse(
        items=items,
        total_count=len(items),
    )


@router.delete(
    "/{id}",
    summary="Delete unbooked counselling slot",
    description="Permanently deletes an unbooked slot. Booked slots return 409 Conflict (must be cancelled).",
)
async def delete_counselling_slot(
    id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    clean_id = str(id).strip()
    slot = await db[COL_COUNSELLING_SLOTS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Counselling slot '{clean_id}' not found.",
        )

    # Only unbooked slots may be deleted
    if slot.get("booked_by_user_id") and slot.get("cancelled_at") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a booked appointment slot. Use POST /{id}/cancel to cancel the booking.",
        )

    await db[COL_COUNSELLING_SLOTS].delete_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    return {"success": True, "message": "Slot deleted successfully."}


@router.post(
    "/{id}/cancel",
    response_model=SlotResponse,
    summary="Cancel a booked slot and notify student",
    description="Frees or cancels a booked appointment slot, notifies the student with neutral copy, and unschedules the intervention.",
)
async def cancel_counselling_slot_by_staff(
    id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SlotResponse:
    clean_id = str(id).strip()
    slot = await db[COL_COUNSELLING_SLOTS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Counselling slot '{clean_id}' not found.",
        )

    now_utc = datetime.now(timezone.utc)
    booked_student_id = slot.get("booked_by_user_id")
    interv_id = slot.get("intervention_id")
    slot_start = slot.get("start_at")

    # If slot was booked, notify student and unschedule intervention
    if booked_student_id:
        try:
            formatted_time = (
                slot_start.strftime("%A, %B %d at %I:%M %p UTC")
                if isinstance(slot_start, datetime)
                else "your scheduled session"
            )
            await create_notification(
                db=db,
                user_id=str(booked_student_id),
                type="appointment_cancelled",
                title="Advisory Appointment Update",
                body=f"Your scheduled counselling consultation for {formatted_time} was cancelled by the counsellor. Please select an alternative slot on your support page.",
                link="/support",
                related_id=interv_id,
            )
        except Exception as exc:
            logger.warning("Failed to notify student of staff slot cancellation: %s", exc)

    if interv_id:
        try:
            await db[COL_INTERVENTION_RECORDS].update_one(
                {"$or": [{"id": interv_id}, {"_id": interv_id}]},
                {"$set": {"scheduled_for": None, "updated_at": now_utc}},
            )
        except Exception as exc:
            logger.warning("Failed to clear scheduled_for on intervention %s: %s", interv_id, exc)

    # Free the slot and mark cancelled
    await db[COL_COUNSELLING_SLOTS].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {
            "$set": {
                "booked_by_user_id": None,
                "intervention_id": None,
                "booked_at": None,
                "cancelled_at": now_utc,
            }
        },
    )

    updated_slot = await db[COL_COUNSELLING_SLOTS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    sid = str(updated_slot.get("id") or updated_slot.get("_id"))
    counsellor_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None)

    return SlotResponse(
        id=sid,
        counsellor_id=str(updated_slot.get("counsellor_id", "")),
        counsellor_name=counsellor_name,
        start_at=updated_slot.get("start_at", now_utc),
        duration_minutes=int(updated_slot.get("duration_minutes", 45)),
        mode=updated_slot.get("mode", "online"),
        location_or_link=updated_slot.get("location_or_link"),
        is_booked=False,
        booked_by_user_id=None,
        intervention_id=None,
        booked_at=None,
        cancelled_at=updated_slot.get("cancelled_at"),
        created_at=updated_slot.get("created_at", now_utc),
    )
