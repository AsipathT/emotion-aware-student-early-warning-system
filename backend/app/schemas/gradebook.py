import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GradebookEntryBase(BaseModel):
    item_type: str = Field(..., pattern="^(assignment|quiz|exam|manual)$")
    item_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=255)
    score: float = Field(..., ge=0)
    max_score: float = Field(..., gt=0)
    weight: float = Field(default=1.0, ge=0)


class GradebookEntryCreate(GradebookEntryBase):
    student_id: uuid.UUID


class GradebookEntryResponse(GradebookEntryBase):
    id: uuid.UUID
    course_id: uuid.UUID
    student_id: uuid.UUID
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
