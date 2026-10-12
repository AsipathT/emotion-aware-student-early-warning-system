import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class Assignment(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    max_score: float = 100.0
    weight: float = 1.0
    is_published: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["course_id"] = str(d["course_id"])
        return d


class AssignmentSubmission(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_text: Optional[str] = None
    file_url: Optional[str] = None
    score: Optional[float] = None
    feedback: Optional[str] = None
    graded_by: Optional[uuid.UUID] = None
    graded_at: Optional[datetime] = None
    is_late: bool = False
    delay_days: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["assignment_id"] = str(d["assignment_id"])
        d["student_id"] = str(d["student_id"])
        if d.get("graded_by"):
            d["graded_by"] = str(d["graded_by"])
        return d


class QuizOption(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    text: str
    is_correct: bool = False
    order: int = 1

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["id"] = str(d["id"])
        return d


class QuizQuestion(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    quiz_id: uuid.UUID
    text: str
    question_type: str
    points: float = 1.0
    order: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    options: List[QuizOption] = Field(default_factory=list)

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["quiz_id"] = str(d["quiz_id"])
        d["options"] = [opt.to_mongo() if hasattr(opt, "to_mongo") else opt for opt in self.options]
        return d


class Quiz(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None
    max_attempts: int = 1
    max_score: float = 100.0
    weight: float = 1.0
    is_published: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["course_id"] = str(d["course_id"])
        return d


class QuizAttempt(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["quiz_id"] = str(d["quiz_id"])
        d["student_id"] = str(d["student_id"])
        return d


class QuizAnswer(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    selected_option_id: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(d.pop("id"))
        d["attempt_id"] = str(d["attempt_id"])
        d["question_id"] = str(d["question_id"])
        if d.get("selected_option_id"):
            d["selected_option_id"] = str(d["selected_option_id"])
        return d
