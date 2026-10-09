import asyncio
from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment

async def seed():
    async with AsyncSessionLocal() as db:
        # Find the admin user
        result = await db.execute(select(User).where(User.email == 'admin@lms.edu'))
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            print("Admin user not found. Run alembic upgrade head first.")
            return

        # Create a course
        course_id = uuid.uuid4()
        course = Course(
            id=course_id,
            title="Introduction to Machine Learning",
            description="A comprehensive introduction to ML concepts, supervised and unsupervised learning.",
            is_published=True,
            start_date=datetime.now(timezone.utc).date(),
            lecturer_id=admin_user.id
        )
        db.add(course)
        
        # Enroll the admin in the course
        enrollment = Enrollment(
            user_id=admin_user.id,
            course_id=course_id,
            status="active"
        )
        db.add(enrollment)
        
        await db.commit()
        print(f"Successfully created course '{course.title}' and enrolled admin@lms.edu.")

if __name__ == "__main__":
    asyncio.run(seed())
