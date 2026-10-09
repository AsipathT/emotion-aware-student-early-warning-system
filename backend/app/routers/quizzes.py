import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.assessment import Quiz, QuizAnswer, QuizAttempt, QuizOption, QuizQuestion
from app.models.course import Course
from app.models.user import User
from app.schemas.assessment import (
    QuizAnswerCreate, QuizAttemptResponse, QuizCreate, QuizQuestionCreate,
    QuizQuestionResponse, QuizResponse, QuizUpdate
)

router = APIRouter(prefix="/api/v1/courses", tags=["quizzes"])


@router.post("/{course_id}/quizzes", response_model=QuizResponse)
async def create_quiz(
    course_id: uuid.UUID,
    quiz_in: QuizCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = Quiz(course_id=course_id, **quiz_in.model_dump())
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)
    return quiz


@router.get("/{course_id}/quizzes", response_model=List[QuizResponse])
async def list_quizzes(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Quiz).where(Quiz.course_id == course_id)
    if current_user.role == "student":
        stmt = stmt.where(Quiz.is_published == True)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{course_id}/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.course_id != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    if current_user.role == "student" and not quiz.is_published:
        raise HTTPException(status_code=403, detail="Quiz not published")
        
    return quiz


@router.patch("/{course_id}/quizzes/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    quiz_in: QuizUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.course_id != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    update_data = quiz_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(quiz, field, value)
        
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)
    return quiz


@router.post("/{course_id}/quizzes/{quiz_id}/questions", response_model=QuizQuestionResponse)
async def add_quiz_question(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    question_in: QuizQuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.course_id != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")

    q_data = question_in.model_dump(exclude={"options"})
    question = QuizQuestion(quiz_id=quiz_id, **q_data)
    db.add(question)
    await db.flush()
    await db.refresh(question)

    for opt_in in question_in.options:
        option = QuizOption(question_id=question.id, **opt_in.model_dump())
        db.add(option)
    
    await db.flush()
    # Eager load options to return
    stmt = select(QuizQuestion).options(selectinload(QuizQuestion.options)).where(QuizQuestion.id == question.id).execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.scalar_one()


@router.post("/{course_id}/quizzes/{quiz_id}/start", response_model=QuizAttemptResponse)
async def start_quiz_attempt(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.course_id != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    if not quiz.is_published:
        raise HTTPException(status_code=403, detail="Quiz not published")

    # Check attempt limit
    stmt = select(func.count(QuizAttempt.id)).where(
        QuizAttempt.quiz_id == quiz_id,
        QuizAttempt.student_id == current_user.id
    )
    result = await db.execute(stmt)
    attempt_count = result.scalar() or 0
    if attempt_count >= quiz.max_attempts:
        raise HTTPException(status_code=403, detail="Maximum attempts reached")

    attempt = QuizAttempt(quiz_id=quiz_id, student_id=current_user.id)
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt


@router.post("/{course_id}/quizzes/{quiz_id}/attempts/{attempt_id}/answer", status_code=status.HTTP_201_CREATED)
async def submit_quiz_answer(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    attempt_id: uuid.UUID,
    answer_in: QuizAnswerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.quiz_id != quiz_id or attempt.student_id != current_user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    # Upsert logic - check if answer exists for this question in this attempt
    stmt = select(QuizAnswer).where(
        QuizAnswer.attempt_id == attempt_id,
        QuizAnswer.question_id == answer_in.question_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.selected_option_id = answer_in.selected_option_id
        db.add(existing)
    else:
        answer = QuizAnswer(
            attempt_id=attempt_id,
            question_id=answer_in.question_id,
            selected_option_id=answer_in.selected_option_id
        )
        db.add(answer)
        
    await db.flush()
    return {"status": "ok"}


@router.post("/{course_id}/quizzes/{quiz_id}/attempts/{attempt_id}/submit", response_model=QuizAttemptResponse)
async def submit_quiz_attempt(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.quiz_id != quiz_id or attempt.student_id != current_user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    from datetime import datetime, timezone
    attempt.submitted_at = datetime.now(timezone.utc)
    
    # Auto-grade
    stmt = select(QuizAnswer).where(QuizAnswer.attempt_id == attempt_id)
    result = await db.execute(stmt)
    answers = result.scalars().all()
    
    total_score = 0.0
    for ans in answers:
        if ans.selected_option_id:
            opt = await db.get(QuizOption, ans.selected_option_id)
            q = await db.get(QuizQuestion, ans.question_id)
            if opt and opt.is_correct and q:
                total_score += q.points
                
    attempt.score = total_score
    db.add(attempt)
    await db.flush()

    # Upsert GradebookEntry for this quiz + student
    from app.models.gradebook import GradebookEntry
    quiz = await db.get(Quiz, quiz_id)
    gb_stmt = select(GradebookEntry).where(
        GradebookEntry.course_id == course_id,
        GradebookEntry.student_id == current_user.id,
        GradebookEntry.item_type == "quiz",
        GradebookEntry.item_id == quiz_id
    )
    gb_result = await db.execute(gb_stmt)
    gb_entry = gb_result.scalar_one_or_none()

    if gb_entry:
        # Keep best score
        if total_score > gb_entry.score:
            gb_entry.score = total_score
    else:
        gb_entry = GradebookEntry(
            course_id=course_id,
            student_id=current_user.id,
            item_type="quiz",
            item_id=quiz_id,
            title=quiz.title,
            score=total_score,
            max_score=quiz.max_score,
            weight=quiz.weight,
        )
        db.add(gb_entry)

    await db.flush()
    await db.refresh(attempt)
    return attempt


@router.get("/{course_id}/quizzes/{quiz_id}/attempts", response_model=List[QuizAttemptResponse])
async def list_quiz_attempts(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("lecturer", "admin"))
):
    stmt = select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{course_id}/quizzes/{quiz_id}/attempts/mine", response_model=List[QuizAttemptResponse])
async def list_my_quiz_attempts(
    course_id: uuid.UUID,
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student"))
):
    stmt = select(QuizAttempt).where(
        QuizAttempt.quiz_id == quiz_id,
        QuizAttempt.student_id == current_user.id
    )
    result = await db.execute(stmt)
    return result.scalars().all()
