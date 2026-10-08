import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserSessionCreate(BaseModel):
    ip_address: Optional[str] = None
    user_agent: Optional[str] = Field(None, max_length=512)


class UserSessionUpdate(BaseModel):
    """Used for heartbeat to update last_seen_at"""
    pass


class UserSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    login_at: datetime
    last_seen_at: Optional[datetime] = None
    logout_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClickEventCreate(BaseModel):
    course_id: Optional[uuid.UUID] = None
    module_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    event_type: str = Field(..., max_length=50)
    resource_type: Optional[str] = Field(None, max_length=50)
    resource_id: Optional[uuid.UUID] = None
    payload: Optional[Dict[str, Any]] = None
    client_ts: Optional[datetime] = None


class ClickEventResponse(ClickEventCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkClickEventCreate(BaseModel):
    events: List[ClickEventCreate]
