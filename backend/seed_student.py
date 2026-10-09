import asyncio
from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash

async def seed_student():
    async with AsyncSessionLocal() as db:
        # Create student user
        student_id = uuid.uuid4()
        student = User(
            id=student_id,
            email="student@lms.edu",
            hashed_password=get_password_hash("Student1234"),
            full_name="Student User",
            role="student",
            is_active=True
        )
        db.add(student)
        await db.commit()
        print("Successfully created student@lms.edu.")

if __name__ == "__main__":
    asyncio.run(seed_student())
