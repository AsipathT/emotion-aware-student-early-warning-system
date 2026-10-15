"""
backend/app/routers/quizzes.py

Feature 11: Quizzes and Attempts Management.
Operates strictly on 'lms_*' collections:
  - lms_quizzes
  - lms_quiz_attempts
  - lms_gradebook
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.schema_mapping import (
    COL_GRADEBOOK,
    COL_QUIZ_ATTEMPTS,
    COL_QUIZZES,
    check_course_ownership,
    check_student_enrolled,
)
from app.models.gradebook import GradebookEntry
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/v1/courses", tags=["quizzes"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class QuizOptionIn(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., max_length=1000)
    is_correct: bool = False
    order: int = 1


class QuizQuestionIn(BaseModel):
    id: Optional[str] = None
    text: str
    question_type: str = Field(..., pattern="^(mcq|true_false)$")
    points: float = Field(default=1.0, ge=0)
    order: int = 1
    options: List[QuizOptionIn] = []


class QuizCreateIn(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    max_attempts: int = Field(default=1, gt=0)
    max_score: float = Field(default=100.0, ge=0)
    weight: float = Field(default=1.0, ge=0)
    is_published: bool = False
    questions: List[QuizQuestionIn] = []


class QuizUpdateIn(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    max_attempts: Optional[int] = Field(None, gt=0)
    max_score: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    is_published: Optional[bool] = None
    questions: Optional[List[QuizQuestionIn]] = None


class QuizAttemptStartIn(BaseModel):
    pass


class QuizAttemptSubmitIn(BaseModel):
    answers: Dict[str, str] = Field(default_factory=dict, description="question_id -> selected_option_id")


def strip_correct_answers(quiz_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes quiz document for students: ensures is_correct is NEVER leaked."""
    sanitized = dict(quiz_doc)
    sanitized_questions = []
    for q in sanitized.get("questions", []):
        clean_q = dict(q)
        clean_opts = []
        for opt in clean_q.get("options", []):
            clean_opt = dict(opt)
            clean_opt.pop("is_correct", None)
            clean_opts.append(clean_opt)
        clean_q["options"] = clean_opts
        clean_q.pop("correct_answer", None)
        sanitized_questions.append(clean_q)
    sanitized["questions"] = sanitized_questions
    return sanitized


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{course_id}/quizzes", status_code=status.HTTP_201_CREATED)
async def create_quiz(
    course_id: str,
    quiz_in: QuizCreateIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """Create a quiz with embedded questions and options (course owner only)."""
    cid_str = str(course_id)
    await check_course_ownership(db, cid_str, current_user)

    qid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Prepare questions with unique IDs if omitted
    processed_questions = []
    for q in quiz_in.questions:
        q_dict = q.model_dump()
        q_dict["id"] = q_dict.get("id") or str(uuid.uuid4())
        processed_opts = []
        for opt in q_dict.get("options", []):
            opt_dict = dict(opt)
            opt_dict["id"] = opt_dict.get("id") or str(uuid.uuid4())
            processed_opts.append(opt_dict)
        q_dict["options"] = processed_opts
        processed_questions.append(q_dict)

    quiz_doc = {
        "_id": qid,
        "id": qid,
        "course_id": cid_str,
        "title": quiz_in.title,
        "description": quiz_in.description,
        "open_at": quiz_in.open_at,
        "close_at": quiz_in.close_at,
        "time_limit_minutes": quiz_in.time_limit_minutes,
        "max_attempts": quiz_in.max_attempts,
        "max_score": quiz_in.max_score,
        "weight": quiz_in.weight,
        "is_published": quiz_in.is_published,
        "questions": processed_questions,
        "created_at": now,
        "updated_at": now,
    }

    await db[COL_QUIZZES].insert_one(quiz_doc)
    return quiz_doc


@router.get("/{course_id}/quizzes")
async def list_quizzes(
    course_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List quizzes. Students only see published ones with is_correct stripped."""
    cid_str = str(course_id)
    filter_q: Dict[str, Any] = {"course_id": cid_str}

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val == "student":
        filter_q["is_published"] = True

    cursor = db[COL_QUIZZES].find(filter_q)
    docs = await cursor.to_list(length=1000)
    result = []
    for doc in docs:
        doc["id"] = doc.pop("_id")
        if role_val == "student":
            doc = strip_correct_answers(doc)
        result.append(doc)
    return result


@router.get("/{course_id}/quizzes/{quiz_id}")
async def get_quiz(
    course_id: str,
    quiz_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get single quiz. is_correct is stripped for students."""
    cid_str = str(course_id)
    qid_str = str(quiz_id)

    doc = await db[COL_QUIZZES].find_one({"_id": qid_str, "course_id": cid_str})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val == "student":
        if not doc.get("is_published"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quiz not published")
        doc = strip_correct_answers(doc)

    doc["id"] = doc.pop("_id")
    return doc


@router.patch("/{course_id}/quizzes/{quiz_id}")
async def update_quiz(
    course_id: str,
    quiz_id: str,
    quiz_in: QuizUpdateIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> Dict[str, Any]:
    """Update quiz (course owner only)."""
    cid_str = str(course_id)
    qid_str = str(quiz_id)
    await check_course_ownership(db, cid_str, current_user)

    doc = await db[COL_QUIZZES].find_one({"_id": qid_str, "course_id": cid_str})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    update_data = quiz_in.model_dump(exclude_unset=True)
    if "questions" in update_data and update_data["questions"] is not None:
        processed_questions = []
        for q in update_data["questions"]:
            q_dict = dict(q)
            q_dict["id"] = q_dict.get("id") or str(uuid.uuid4())
            processed_opts = []
            for opt in q_dict.get("options", []):
                opt_dict = dict(opt)
                opt_dict["id"] = opt_dict.get("id") or str(uuid.uuid4())
                processed_opts.append(opt_dict)
            q_dict["options"] = processed_opts
            processed_questions.append(q_dict)
        update_data["questions"] = processed_questions

    update_data["updated_at"] = datetime.now(timezone.utc)
    await db[COL_QUIZZES].update_one({"_id": qid_str}, {"$set": update_data})

    updated = await db[COL_QUIZZES].find_one({"_id": qid_str})
    updated["id"] = updated.pop("_id")
    return updated


@router.delete("/{course_id}/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    course_id: str,
    quiz_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> None:
    """Delete quiz (course owner only)."""
    cid_str = str(course_id)
    qid_str = str(quiz_id)
    await check_course_ownership(db, cid_str, current_user)

    doc = await db[COL_QUIZZES].find_one({"_id": qid_str, "course_id": cid_str})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    await db[COL_QUIZZES].delete_one({"_id": qid_str})
    return None


@router.post("/{course_id}/quizzes/{quiz_id}/attempts", status_code=status.HTTP_201_CREATED)
async def start_quiz_attempt(
    course_id: str,
    quiz_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Dict[str, Any]:
    """
    Student begins a quiz attempt.
    Enforces course enrollment, open/close window, and max_attempts.
    """
    cid_str = str(course_id)
    qid_str = str(quiz_id)
    uid_str = str(current_user.id)

    is_enrolled = await check_student_enrolled(db, cid_str, current_user)
    if not is_enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course.")

    quiz_doc = await db[COL_QUIZZES].find_one({"_id": qid_str, "course_id": cid_str})
    if not quiz_doc or not quiz_doc.get("is_published"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not available.")

    now = datetime.now(timezone.utc)

    # Window check
    open_at = quiz_doc.get("open_at")
    if open_at:
        if open_at.tzinfo is None:
            open_at = open_at.replace(tzinfo=timezone.utc)
        if now < open_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz is not yet open.")

    close_at = quiz_doc.get("close_at")
    if close_at:
        if close_at.tzinfo is None:
            close_at = close_at.replace(tzinfo=timezone.utc)
        if now > close_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz window has closed.")

    # Max attempts check
    max_attempts = int(quiz_doc.get("max_attempts", 1))
    existing_count = await db[COL_QUIZ_ATTEMPTS].count_documents({
        "quiz_id": qid_str,
        "student_id": uid_str,
        "submitted": True,
    })
    if existing_count >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum attempts ({max_attempts}) reached for this quiz.",
        )

    attempt_id = str(uuid.uuid4())
    attempt_doc = {
        "_id": attempt_id,
        "id": attempt_id,
        "quiz_id": qid_str,
        "course_id": cid_str,
        "student_id": uid_str,
        "started_at": now,
        "time_limit_minutes": quiz_doc.get("time_limit_minutes"),
        "submitted": False,
        "completed_at": None,
        "answers": {},
        "score": None,
        "max_score": float(quiz_doc.get("max_score", 100.0)),
    }

    await db[COL_QUIZ_ATTEMPTS].insert_one(attempt_doc)
    return attempt_doc


@router.post("/{course_id}/quizzes/{quiz_id}/attempts/{attempt_id}/submit")
async def submit_quiz_attempt(
    course_id: str,
    quiz_id: str,
    attempt_id: str,
    submit_in: QuizAttemptSubmitIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> Dict[str, Any]:
    """
    Submit quiz attempt.
    Performs server-side auto-grade and automatically upserts a lms_gradebook document.
    """
    cid_str = str(course_id)
    qid_str = str(quiz_id)
    att_str = str(attempt_id)
    uid_str = str(current_user.id)

    attempt = await db[COL_QUIZ_ATTEMPTS].find_one({
        "_id": att_str,
        "quiz_id": qid_str,
        "student_id": uid_str,
    })
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    if attempt.get("submitted"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt already submitted.")

    quiz_doc = await db[COL_QUIZZES].find_one({"_id": qid_str})
    if not quiz_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    now = datetime.now(timezone.utc)

    # Server-side auto-grading
    questions = quiz_doc.get("questions", [])
    total_points_possible = sum(float(q.get("points", 1.0)) for q in questions)
    earned_points = 0.0

    user_answers = submit_in.answers or {}
    for q in questions:
        q_id = str(q.get("id"))
        chosen_opt_id = user_answers.get(q_id)
        if not chosen_opt_id:
            continue

        for opt in q.get("options", []):
            if str(opt.get("id")) == str(chosen_opt_id) and opt.get("is_correct") is True:
                earned_points += float(q.get("points", 1.0))
                break

    quiz_max_score = float(quiz_doc.get("max_score", 100.0))
    if total_points_possible > 0:
        final_score = round((earned_points / total_points_possible) * quiz_max_score, 2)
    else:
        final_score = 0.0

    update_fields = {
        "submitted": True,
        "completed_at": now,
        "answers": user_answers,
        "score": final_score,
        "earned_points": earned_points,
        "total_possible_points": total_points_possible,
    }
    await db[COL_QUIZ_ATTEMPTS].update_one({"_id": att_str}, {"$set": update_fields})

    # Upsert lms_gradebook document (item_type: 'quiz')
    gb_filter = {
        "course_id": cid_str,
        "student_id": uid_str,
        "item_type": "quiz",
        "item_id": qid_str,
    }
    weight = float(quiz_doc.get("weight", 1.0))
    gb_entry = await db[COL_GRADEBOOK].find_one(gb_filter)
    if gb_entry:
        await db[COL_GRADEBOOK].update_one(
            {"_id": gb_entry["_id"]},
            {
                "$set": {
                    "score": final_score,
                    "max_score": quiz_max_score,
                    "weight": weight,
                    "recorded_at": now,
                    "updated_at": now,
                }
            },
        )
    else:
        new_gb_entry = GradebookEntry(
            course_id=course_id,
            student_id=current_user.id,
            item_type="quiz",
            item_id=quiz_id,
            title=quiz_doc.get("title", "Quiz"),
            score=final_score,
            max_score=quiz_max_score,
            weight=weight,
            recorded_at=now,
        )
        await db[COL_GRADEBOOK].insert_one(new_gb_entry.to_mongo())

    updated_att = await db[COL_QUIZ_ATTEMPTS].find_one({"_id": att_str})
    updated_att["id"] = updated_att.pop("_id")
    return updated_att


@router.get("/{course_id}/quizzes/{quiz_id}/attempts")
async def list_quiz_attempts(
    course_id: str,
    quiz_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LECTURER, UserRole.ADMIN)),
) -> List[Dict[str, Any]]:
    """Lecturer lists attempts for a quiz (course owner or admin only)."""
    cid_str = str(course_id)
    qid_str = str(quiz_id)
    await check_course_ownership(db, cid_str, current_user)

    cursor = db[COL_QUIZ_ATTEMPTS].find({"quiz_id": qid_str})
    docs = await cursor.to_list(length=1000)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs


@router.get("/{course_id}/quizzes/{quiz_id}/my-attempts")
async def get_my_quiz_attempts(
    course_id: str,
    quiz_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
) -> List[Dict[str, Any]]:
    """Student views their own quiz attempts."""
    qid_str = str(quiz_id)
    uid_str = str(current_user.id)

    cursor = db[COL_QUIZ_ATTEMPTS].find({"quiz_id": qid_str, "student_id": uid_str})
    docs = await cursor.to_list(length=100)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    return docs
