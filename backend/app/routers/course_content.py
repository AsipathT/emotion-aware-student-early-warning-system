"""
backend/app/routers/course_content.py

Feature 8: Course Content Pages and Module Block Editor.
Provides:
  - GET /api/v1/courses/{course_id}/modules/{module_id} (read content page; legacy payload tolerated)
  - PATCH /api/v1/courses/{course_id}/modules/{module_id} (course owner update; block validation on write)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.schema_mapping import (
    CANONICAL_COURSES,
    check_course_ownership,
    check_student_enrolled,
)
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/v1/courses", tags=["course-content"])


class ContentBlock(BaseModel):
    type: str = Field(..., pattern="^(text|video|resource)$")
    body: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    mime_type: Optional[str] = None


class ModuleContentPayload(BaseModel):
    blocks: List[Dict[str, Any]] = Field(default_factory=list)


class ModuleContentUpdate(BaseModel):
    title: Optional[str] = None
    sequence_order: Optional[int] = None
    content_payload: Optional[Dict[str, Any]] = None


def validate_blocks(content_payload: Dict[str, Any]) -> None:
    """Validates block structure strictly on write."""
    blocks = content_payload.get("blocks")
    if blocks is None:
        return
    if not isinstance(blocks, list):
        raise HTTPException(
            status_code=422,
            detail="content_payload 'blocks' must be a list.",
        )

    for idx, b in enumerate(blocks):
        if not isinstance(b, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Block {idx} must be an object.",
            )
        b_type = b.get("type")
        if b_type not in ("text", "video", "resource"):
            raise HTTPException(
                status_code=422,
                detail=f"Block {idx} has invalid type: '{b_type}'. Allowed: text, video, resource.",
            )
        if b_type == "text" and not b.get("body"):
            raise HTTPException(
                status_code=422,
                detail=f"Block {idx} of type 'text' requires a non-empty 'body'.",
            )
        if b_type == "video" and (not b.get("url") or not b.get("title")):
            raise HTTPException(
                status_code=422,
                detail=f"Block {idx} of type 'video' requires 'url' and 'title'.",
            )
        if b_type == "resource" and (not b.get("url") or not b.get("title") or not b.get("mime_type")):
            raise HTTPException(
                status_code=422,
                detail=f"Block {idx} of type 'resource' requires 'url', 'title', and 'mime_type'.",
            )


@router.get("/{course_id}/content", response_model=List[Dict[str, Any]])
async def get_course_modules(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get all modules for a course.
    """
    course_doc = await db[CANONICAL_COURSES].find_one({"$or": [{"_id": course_id}, {"course_id": course_id}, {"id": course_id}]})
    if not course_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    modules = course_doc.get("modules", [])
    result = []
    for m in modules:
        m_dict = dict(m)
        m_dict["id"] = str(m.get("_id") or m.get("id"))
        result.append(m_dict)
    return result


@router.get("/{course_id}/modules/{module_id}", response_model=Dict[str, Any])
async def get_module_content(
    course_id: str,
    module_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get a module content page.
    Enforces course visibility. Unknown or legacy payload formats are returned as-is without failure.
    """
    cid_str = str(course_id)
    mid_str = str(module_id)

    course_doc = await db[CANONICAL_COURSES].find_one({"_id": cid_str})
    if not course_doc:
        course_doc = await db[CANONICAL_COURSES].find_one({"id": cid_str})
    if not course_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val == "student":
        if not course_doc.get("is_published", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Course is not published.")

    modules = course_doc.get("modules", [])
    target_module = next((m for m in modules if str(m.get("_id") or m.get("id")) == mid_str), None)
    if not target_module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    # Ensure format compatibility
    res = dict(target_module)
    res["id"] = res.get("_id") or res.get("id")
    # Legacy payloads returned as-is
    if "content_payload" not in res or res["content_payload"] is None:
        res["content_payload"] = {}

    return res


@router.patch("/{course_id}/modules/{module_id}", response_model=Dict[str, Any])
async def update_module_content(
    course_id: str,
    module_id: str,
    payload: ModuleContentUpdate,
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """
    Course owner (or Admin) patches module content payload.
    Validates content blocks on write.
    """
    cid_str = str(course_id)
    mid_str = str(module_id)

    course_doc = await check_course_ownership(db, cid_str, current_user)
    modules = course_doc.get("modules", [])
    target_idx = next(
        (i for i, m in enumerate(modules) if str(m.get("_id") or m.get("id")) == mid_str),
        None,
    )
    if target_idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    target_module = modules[target_idx]
    now = datetime.now(timezone.utc)

    if payload.title is not None:
        target_module["title"] = payload.title
    if payload.sequence_order is not None:
        target_module["sequence_order"] = payload.sequence_order
    if payload.content_payload is not None:
        validate_blocks(payload.content_payload)
        target_module["content_payload"] = payload.content_payload

    target_module["updated_at"] = now
    modules[target_idx] = target_module

    # Atomic MongoDB arrayFilters update expression ensuring only target module is updated
    await db[CANONICAL_COURSES].update_one(
        {"_id": course_doc["_id"]},
        {
            "$set": {
                "modules.$[elem].title": target_module["title"],
                "modules.$[elem].sequence_order": target_module["sequence_order"],
                "modules.$[elem].content_payload": target_module.get("content_payload", {}),
                "modules.$[elem].updated_at": now,
                "updated_at": now,
            }
        },
        array_filters=[{"$or": [{"elem._id": mid_str}, {"elem.id": mid_str}]}],
    )

    res = dict(target_module)
    res["id"] = res.get("_id") or res.get("id")
    return res
