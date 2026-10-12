import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class GradebookEntry(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: uuid.UUID
    student_id: uuid.UUID
    item_type: str
    item_id: Optional[uuid.UUID] = None
    title: str
    score: float
    max_score: float
    weight: float = 1.0
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["course_id"] = str(d["course_id"])
        d["student_id"] = str(d["student_id"])
        if d.get("item_id"):
            d["item_id"] = str(d["item_id"])
        return d
