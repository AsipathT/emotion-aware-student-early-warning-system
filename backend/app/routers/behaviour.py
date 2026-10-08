import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.behaviour import ClickEvent, UserSession
from app.models.user import User
from app.schemas.behaviour import BulkClickEventCreate


router = APIRouter(prefix="/api/v1/behaviour", tags=["behaviour"])


@router.post("/sessions/{session_id}/heartbeat", status_code=status.HTTP_200_OK)
async def session_heartbeat(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    session = await db.get(UserSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    from datetime import datetime, timezone
    session.last_seen_at = datetime.now(timezone.utc)
    db.add(session)
    await db.flush()
    return {"status": "ok"}


@router.post("/sessions/{session_id}/logout", status_code=status.HTTP_200_OK)
async def session_logout(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    session = await db.get(UserSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    session.logout_at = now
    
    if session.login_at:
        delta = now - session.login_at
        session.duration_seconds = int(delta.total_seconds())
        
    db.add(session)
    await db.flush()
    return {"status": "logged_out"}


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def bulk_ingest_events(
    payload: BulkClickEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    for event_in in payload.events:
        event = ClickEvent(
            user_id=current_user.id,
            **event_in.model_dump()
        )
        db.add(event)
        
    await db.flush()
    return {"status": "ingested", "count": len(payload.events)}
