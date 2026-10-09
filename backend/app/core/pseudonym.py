import hmac
import hashlib
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.models.enrollment import Enrollment

def pseudonymize(user_id: str) -> str:
    """
    Generate a pseudonymous string for a user_id using HMAC-SHA256.
    """
    salt = getattr(settings, 'pseudonym_salt', 'default_safe_dev_salt_1234')
    h = hmac.new(salt.encode('utf-8'), str(user_id).encode('utf-8'), hashlib.sha256)
    return "pseudo_" + h.hexdigest()[:10]

async def resolve_pseudonym(db: AsyncSession, course_id: uuid.UUID, pseudo_id: str) -> Optional[uuid.UUID]:
    """
    Given a pseudonymous ID and a course_id, find the matching enrolled student's UUID.
    """
    result = await db.execute(select(Enrollment.user_id).where(Enrollment.course_id == course_id))
    for (user_id,) in result.fetchall():
        if pseudonymize(str(user_id)) == pseudo_id:
            return user_id
    return None
