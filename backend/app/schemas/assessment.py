import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── ASSIGNMENTS ─────────────────────────────────────────────────────────────

class AssignmentBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    max_score: float = Field(default=100.0, ge=0)
    weight: float = Field(default=1.0, ge=0)
    is_published: bool = False


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    max_score: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    is_published: Optional[bool] = None


class AssignmentResponse(AssignmentBase):
    id: uuid.UUID
    course_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentSubmissionBase(BaseModel):
    content_text: Optional[str] = None
    file_url: Optional[str] = None


class AssignmentSubmissionCreate(AssignmentSubmissionBase):
    pass


class AssignmentSubmissionGrade(BaseModel):
    score: float = Field(..., ge=0)
    feedback: Optional[str] = None


class AssignmentSubmissionResponse(AssignmentSubmissionBase):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime
    score: Optional[float] = None
    feedback: Optional[str] = None
    graded_by: Optional[uuid.UUID] = None
    graded_at: Optional[datetime] = None
    is_late: bool
    delay_days: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── QUIZZES ─────────────────────────────────────────────────────────────────

class QuizOptionBase(BaseModel):
    text: str = Field(..., max_length=1000)
    is_correct: bool = False
    order: int = 1


class QuizOptionCreate(QuizOptionBase):
    pass


class QuizOptionResponse(QuizOptionBase):
    id: uuid.UUID
    question_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class QuizOptionStudentResponse(BaseModel):
    """Option response for students (hides is_correct)."""
    id: uuid.UUID
    question_id: uuid.UUID
    text: str
    order: int

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionBase(BaseModel):
    text: str
    question_type: str = Field(..., pattern="^(mcq|true_false)$")
    points: float = Field(default=1.0, ge=0)
    order: int = 1


class QuizQuestionCreate(QuizQuestionBase):
    options: List[QuizOptionCreate] = []


class QuizQuestionResponse(QuizQuestionBase):
    id: uuid.UUID
    quiz_id: uuid.UUID
    options: List[QuizOptionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionStudentResponse(QuizQuestionBase):
    id: uuid.UUID
    quiz_id: uuid.UUID
    options: List[QuizOptionStudentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class QuizBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    max_attempts: int = Field(default=1, gt=0)
    max_score: float = Field(default=100.0, ge=0)
    weight: float = Field(default=1.0, ge=0)
    is_published: bool = False


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    max_attempts: Optional[int] = Field(None, gt=0)
    max_score: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    is_published: Optional[bool] = None


class QuizResponse(QuizBase):
    id: uuid.UUID
    course_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuizAnswerBase(BaseModel):
    question_id: uuid.UUID
    selected_option_id: Optional[uuid.UUID] = None


class QuizAnswerCreate(QuizAnswerBase):
    pass


class QuizAttemptResponse(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
