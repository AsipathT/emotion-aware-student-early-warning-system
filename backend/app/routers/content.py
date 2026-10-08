import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.course import Course, Module
from app.models.user import User
from app.schemas.course import ModuleResponse


router = APIRouter(prefix="/api/v1/courses", tags=["content"])


@router.get("/{course_id}/content", response_model=List[ModuleResponse])
async def get_course_content(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get all modules and their content payload for a specific course."""
    # Check course exists
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # If student, maybe check if published? (Member 1 logic, we keep it simple here)
    if current_user.role == "student" and not course.is_published:
        raise HTTPException(status_code=403, detail="Course is not published")

    stmt = select(Module).where(Module.course_id == course_id).order_by(Module.sequence_order)
    result = await db.execute(stmt)
    modules = result.scalars().all()
    return modules


@router.patch("/{course_id}/modules/{module_id}/content", response_model=ModuleResponse)
async def update_module_content(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    content_payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
) -> Any:
    """Update a module's content_payload."""
    module = await db.get(Module, module_id)
    if not module or module.course_id != course_id:
        raise HTTPException(status_code=404, detail="Module not found")

    module.content_payload = content_payload
    db.add(module)
    await db.flush()
    await db.refresh(module)
    return module
