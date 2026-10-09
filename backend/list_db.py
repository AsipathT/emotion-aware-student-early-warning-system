import asyncio
from app.core.db import AsyncSessionLocal
from sqlalchemy import select
from app.models.course import Course
from app.models.user import User
from app.models.enrollment import Enrollment
from app.models.analytics import AffectWeekly, RiskScore, TrajectoryLabel, WeeklyFeature
from app.models.behaviour import UserSession, ClickEvent
from app.models.assessment import Assignment, Quiz

async def main():
    async with AsyncSessionLocal() as db:
        def p(name, rows):
            print(f'\n--- {name} ---')
            for r in rows:
                if hasattr(r, 'title'): print(f'ID: {r.id}, Title: {r.title}')
                elif hasattr(r, 'email'): print(f'ID: {r.id}, Email: {r.email}')
                elif hasattr(r, 'course_id'): print(f'ID: {r.id}, Course: {r.course_id}, Student/User: {getattr(r, "student_id", getattr(r, "user_id", ""))}')
                else: print(f'ID: {r.id}')
        
        p('Courses', (await db.execute(select(Course))).scalars().all())
        p('Users', (await db.execute(select(User))).scalars().all())
        p('Enrollments', (await db.execute(select(Enrollment))).scalars().all())
        p('AffectWeekly', (await db.execute(select(AffectWeekly))).scalars().all())
        p('RiskScore', (await db.execute(select(RiskScore))).scalars().all())
        p('TrajectoryLabel', (await db.execute(select(TrajectoryLabel))).scalars().all())
        p('WeeklyFeature', (await db.execute(select(WeeklyFeature))).scalars().all())
        p('UserSession', (await db.execute(select(UserSession))).scalars().all())
        p('ClickEvent', (await db.execute(select(ClickEvent))).scalars().all())
        p('Assignment', (await db.execute(select(Assignment))).scalars().all())
        p('Quiz', (await db.execute(select(Quiz))).scalars().all())

if __name__ == '__main__':
    asyncio.run(main())
