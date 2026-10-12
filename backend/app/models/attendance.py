import uuid
from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class AttendanceSession(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: uuid.UUID
    title: str
    session_date: date
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["course_id"] = str(d["course_id"])
        if d.get("created_by"):
            d["created_by"] = str(d["created_by"])
        d["session_date"] = datetime.combine(d["session_date"], datetime.min.time(), tzinfo=timezone.utc)
        return d


class AttendanceRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    marked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    marked_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["session_id"] = str(d["session_id"])
        d["student_id"] = str(d["student_id"])
        if d.get("marked_by"):
            d["marked_by"] = str(d["marked_by"])
        return d
