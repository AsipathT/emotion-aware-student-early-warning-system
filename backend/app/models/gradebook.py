import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from pydantic import BaseModel, Field


class GradebookEntry(BaseModel):
    id: Union[uuid.UUID, str] = Field(default_factory=lambda: str(uuid.uuid4()))
    course_id: Union[uuid.UUID, str]
    student_id: Union[uuid.UUID, str]
    item_type: str
    item_id: Optional[Union[uuid.UUID, str]] = None
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
