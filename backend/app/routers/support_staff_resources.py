"""
backend/app/routers/support_staff_resources.py

Feature 38-C: Staff Support Resources & Referral Sharing Router.
Prefix: /api/v1/support/resources
Allows counsellors and administrators to:
  1. Manage library of learning resources, study skills guidance, and campus referrals
  2. Filter resources by resource_type, intervention_type, and active status
  3. Share active resources with students during intervention delivery
  4. Notify students neutrally and record immutable sharing records
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.models.intervention_record import COL_INTERVENTION_RECORDS
from app.models.support_resource import (
    COL_SUPPORT_RESOURCES,
    RESOURCE_TYPE_REFERRAL,
    VALID_RESOURCE_TYPES,
)
from app.models.user import User
from app.schemas.audit import AuditOutcome
from app.schemas.staff_resources import (
    ResourceCreate,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdate,
    SharedResourceItemDetail,
    SharedResourceListResponse,
    ShareResourceRequest,
)
from app.services.audit import log_event
from app.services.notification_service import notify_pid
from app.services.staff_access import require_staff

logger = logging.getLogger("app.support_staff_resources")

router = APIRouter(
    prefix="/api/v1/support/resources",
    tags=["Support Resources"],
)


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create support resource or referral",
    description="Adds a new learning resource, time-management guide, or campus referral to the library.",
)
async def create_support_resource(
    payload: ResourceCreate,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResourceResponse:
    now_utc = datetime.now(timezone.utc)
    res_id = str(uuid.uuid4())

    doc = {
        "_id": res_id,
        "id": res_id,
        "title": payload.title,
        "description": payload.description,
        "resource_type": payload.resource_type,
        "url": payload.url,
        "contact_info": payload.contact_info,
        "intervention_types": [it.strip().lower() for it in payload.intervention_types if it.strip()],
        "is_active": payload.is_active,
        "created_by": str(current_user.id),
        "created_at": now_utc,
        "updated_at": now_utc,
    }

    await db[COL_SUPPORT_RESOURCES].insert_one(doc)

    return ResourceResponse(
        id=res_id,
        title=doc["title"],
        description=doc["description"],
        resource_type=doc["resource_type"],
        url=doc["url"],
        contact_info=doc["contact_info"],
        intervention_types=doc["intervention_types"],
        is_active=doc["is_active"],
        created_by=doc["created_by"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get(
    "",
    response_model=ResourceListResponse,
    summary="List support resources with filters",
    description="Retrieves cataloged resources with optional filtering by type, intervention_type, and active status.",
)
async def list_support_resources(
    type: Optional[str] = Query(default=None, description="Filter by resource_type: resource | guidance | referral"),
    intervention_type: Optional[str] = Query(default=None, description="Filter by associated intervention type"),
    active: Optional[bool] = Query(default=None, description="Filter by is_active status"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResourceListResponse:
    filter_query = {}

    if type is not None and type.strip():
        filter_query["resource_type"] = type.strip().lower()

    if intervention_type is not None and intervention_type.strip():
        filter_query["intervention_types"] = intervention_type.strip().lower()

    if active is not None:
        filter_query["is_active"] = active

    cursor = db[COL_SUPPORT_RESOURCES].find(filter_query).sort("created_at", -1)

    items: List[ResourceResponse] = []
    async for doc in cursor:
        rid = str(doc.get("id") or doc.get("_id"))
        items.append(
            ResourceResponse(
                id=rid,
                title=doc.get("title", ""),
                description=doc.get("description", ""),
                resource_type=doc.get("resource_type", "resource"),
                url=doc.get("url"),
                contact_info=doc.get("contact_info"),
                intervention_types=doc.get("intervention_types", []),
                is_active=doc.get("is_active", True),
                created_by=str(doc.get("created_by", "")),
                created_at=doc.get("created_at", datetime.now(timezone.utc)),
                updated_at=doc.get("updated_at"),
            )
        )

    return ResourceListResponse(
        items=items,
        total_count=len(items),
    )


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get support resource by ID",
)
async def get_support_resource(
    resource_id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResourceResponse:
    clean_id = str(resource_id).strip()
    doc = await db[COL_SUPPORT_RESOURCES].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support resource '{clean_id}' not found.",
        )

    rid = str(doc.get("id") or doc.get("_id"))
    return ResourceResponse(
        id=rid,
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        resource_type=doc.get("resource_type", "resource"),
        url=doc.get("url"),
        contact_info=doc.get("contact_info"),
        intervention_types=doc.get("intervention_types", []),
        is_active=doc.get("is_active", True),
        created_by=str(doc.get("created_by", "")),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at"),
    )


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update support resource or toggle active status",
    description="Modifies fields or deactivates a resource. Does not hard-delete to preserve historical sharing links.",
)
async def update_support_resource(
    resource_id: str,
    payload: ResourceUpdate,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResourceResponse:
    clean_id = str(resource_id).strip()
    doc = await db[COL_SUPPORT_RESOURCES].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support resource '{clean_id}' not found.",
        )

    now_utc = datetime.now(timezone.utc)
    update_data = {"updated_at": now_utc}

    if payload.title is not None:
        update_data["title"] = payload.title
    if payload.description is not None:
        update_data["description"] = payload.description
    if payload.resource_type is not None:
        update_data["resource_type"] = payload.resource_type
    if payload.url is not None:
        update_data["url"] = payload.url
    if payload.contact_info is not None:
        update_data["contact_info"] = payload.contact_info
    if payload.intervention_types is not None:
        update_data["intervention_types"] = [
            it.strip().lower() for it in payload.intervention_types if it.strip()
        ]
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active

    # Verify at least one of url or contact_info remains valid
    resulting_url = update_data.get("url", doc.get("url"))
    resulting_contact = update_data.get("contact_info", doc.get("contact_info"))
    if not (resulting_url and resulting_url.strip()) and not (resulting_contact and resulting_contact.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of 'url' or 'contact_info' must remain present.",
        )

    await db[COL_SUPPORT_RESOURCES].update_one(
        {"$or": [{"id": clean_id}, {"_id": clean_id}]},
        {"$set": update_data},
    )

    updated_doc = await db[COL_SUPPORT_RESOURCES].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    rid = str(updated_doc.get("id") or updated_doc.get("_id"))
    return ResourceResponse(
        id=rid,
        title=updated_doc.get("title", ""),
        description=updated_doc.get("description", ""),
        resource_type=updated_doc.get("resource_type", "resource"),
        url=updated_doc.get("url"),
        contact_info=updated_doc.get("contact_info"),
        intervention_types=updated_doc.get("intervention_types", []),
        is_active=updated_doc.get("is_active", True),
        created_by=str(updated_doc.get("created_by", "")),
        created_at=updated_doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=updated_doc.get("updated_at"),
    )


@router.get(
    "/interventions/{intervention_id}/shared",
    response_model=SharedResourceListResponse,
    summary="Get shared resources for an intervention",
    description="Retrieves the list of learning materials and referrals shared with this intervention, with viewed status.",
)
async def get_intervention_shared_resources(
    intervention_id: str,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SharedResourceListResponse:
    clean_id = str(intervention_id).strip()
    rec = await db[COL_INTERVENTION_RECORDS].find_one({"$or": [{"id": clean_id}, {"_id": clean_id}]})
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_id}' not found.",
        )

    shared_entries = rec.get("shared_resources") or []
    if not shared_entries:
        return SharedResourceListResponse(items=[], total_count=0)

    # Collect resource IDs and query catalog
    res_ids = [str(e.get("resource_id")) for e in shared_entries if e.get("resource_id")]
    cursor = db[COL_SUPPORT_RESOURCES].find({"$or": [{"id": {"$in": res_ids}}, {"_id": {"$in": res_ids}}]})
    res_map = {}
    async for r in cursor:
        key = str(r.get("id") or r.get("_id"))
        res_map[key] = r

    items: List[SharedResourceItemDetail] = []
    for entry in shared_entries:
        rid = str(entry.get("resource_id"))
        meta = res_map.get(rid) or {}
        items.append(
            SharedResourceItemDetail(
                resource_id=rid,
                title=meta.get("title") or "Learning Material",
                description=meta.get("description") or "",
                resource_type=meta.get("resource_type") or "resource",
                url=meta.get("url"),
                contact_info=meta.get("contact_info"),
                shared_at=entry.get("shared_at", datetime.now(timezone.utc)),
                shared_by=str(entry.get("shared_by", "")),
                viewed_at=entry.get("viewed_at"),
                message=entry.get("message"),
            )
        )

    return SharedResourceListResponse(
        items=items,
        total_count=len(items),
    )


@router.post(
    "/interventions/{intervention_id}/share",
    response_model=SharedResourceItemDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Share resource with student intervention",
    description="Shares an active learning resource or referral with an accepted or in-progress intervention (or offered for referrals).",
)
async def share_resource_with_intervention(
    intervention_id: str,
    payload: ShareResourceRequest,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SharedResourceItemDetail:
    clean_interv_id = str(intervention_id).strip()
    clean_res_id = str(payload.resource_id).strip()

    # 1. Fetch resource and verify active
    res = await db[COL_SUPPORT_RESOURCES].find_one(
        {"$or": [{"id": clean_res_id}, {"_id": clean_res_id}]}
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support resource '{clean_res_id}' not found.",
        )

    if not res.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive resource cannot be shared with students.",
        )

    # 2. Fetch intervention record
    rec = await db[COL_INTERVENTION_RECORDS].find_one(
        {"$or": [{"id": clean_interv_id}, {"_id": clean_interv_id}]}
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention record '{clean_interv_id}' not found.",
        )

    # 3. Check intervention status eligibility
    current_status = str(rec.get("status", "")).strip().lower()
    res_type = str(res.get("resource_type", "")).strip().lower()

    if res_type == RESOURCE_TYPE_REFERRAL:
        allowed_statuses = ["accepted", "in_progress", "offered"]
    else:
        allowed_statuses = ["accepted", "in_progress"]

    if current_status not in allowed_statuses:
        allowed_desc = (
            "'accepted', 'in_progress', or 'offered' (for referrals)"
            if res_type == RESOURCE_TYPE_REFERRAL
            else "'accepted' or 'in_progress'"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intervention in state '{current_status}' cannot receive {res_type} shares. State must be {allowed_desc}.",
        )

    # 4. Enforce no duplicate share
    canonical_res_id = str(res.get("id") or res.get("_id"))
    existing_shares = rec.get("shared_resources") or []
    for entry in existing_shares:
        if str(entry.get("resource_id")) == canonical_res_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Resource '{res.get('title')}' has already been shared with this intervention.",
            )

    # 5. Store shared resource entry on intervention_records
    now_utc = datetime.now(timezone.utc)
    new_share_entry = {
        "resource_id": canonical_res_id,
        "shared_at": now_utc,
        "shared_by": str(current_user.id),
        "viewed_at": None,
        "message": payload.message,
    }

    await db[COL_INTERVENTION_RECORDS].update_one(
        {"$or": [{"id": clean_interv_id}, {"_id": clean_interv_id}]},
        {
            "$push": {"shared_resources": new_share_entry},
            "$set": {"updated_at": now_utc},
        },
    )

    # 6. Notify student neutrally (resource_shared template)
    try:
        student_pid = rec.get("pid")
        if student_pid:
            await notify_pid(
                db=db,
                pid=str(student_pid),
                template_key="resource_shared",
                link="/support",
                related_id=clean_interv_id,
            )
    except Exception as exc:
        logger.warning(
            "Failed to dispatch resource_shared notification to student for intervention '%s': %s",
            clean_interv_id,
            exc,
        )

    # 7. Audit log (exception-safe)
    try:
        actor_role_str = str(getattr(current_user.role, "value", current_user.role))
        await log_event(
            request=request,
            db=db,
            action="INTERVENTION_RESOURCE_SHARED",
            actor_id=str(current_user.id),
            actor_role=actor_role_str,
            target_type="intervention",
            target_id=clean_interv_id,
            outcome=AuditOutcome.SUCCESS,
            details={
                "intervention_id": clean_interv_id,
                "resource_id": canonical_res_id,
                "resource_type": res_type,
                "has_message": bool(payload.message),
            },
        )
    except Exception as exc:
        logger.warning("Audit logging failed for resource share: %s", exc)

    return SharedResourceItemDetail(
        resource_id=canonical_res_id,
        title=res.get("title", ""),
        description=res.get("description", ""),
        resource_type=res_type,
        url=res.get("url"),
        contact_info=res.get("contact_info"),
        shared_at=now_utc,
        shared_by=str(current_user.id),
        viewed_at=None,
        message=payload.message,
    )
