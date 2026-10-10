import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UserSession(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: Optional[datetime] = None
    logout_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["user_id"] = str(d["user_id"])
        return d


class ClickEvent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    course_id: Optional[uuid.UUID] = None
    module_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    event_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[uuid.UUID] = None
    payload: Optional[Dict[str, Any]] = None
    client_ts: Optional[datetime] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["user_id"] = str(d["user_id"])
        if d.get("course_id"):
            d["course_id"] = str(d["course_id"])
        if d.get("module_id"):
            d["module_id"] = str(d["module_id"])
        if d.get("session_id"):
            d["session_id"] = str(d["session_id"])
        if d.get("resource_id"):
            d["resource_id"] = str(d["resource_id"])
        return d
