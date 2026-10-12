import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AttendanceSessionBase(BaseModel):
    title: str = Field(..., max_length=255)
    session_date: date


class AttendanceSessionCreate(AttendanceSessionBase):
    pass


class AttendanceSessionResponse(AttendanceSessionBase):
    id: uuid.UUID
    course_id: uuid.UUID
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceRecordBase(BaseModel):
    status: str = Field(..., pattern="^(present|late|absent|excused)$")


class AttendanceRecordCreate(AttendanceRecordBase):
    student_id: uuid.UUID


class AttendanceRecordResponse(AttendanceRecordBase):
    id: uuid.UUID
    session_id: uuid.UUID
    student_id: uuid.UUID
    marked_at: datetime
    marked_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkAttendanceMark(BaseModel):
    records: List[AttendanceRecordCreate]
