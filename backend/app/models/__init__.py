"""
backend/app/models/__init__.py

Exports all MongoDB document models.
"""

from app.models.user import User, UserRole
from app.models.profile import Profile
from app.models.course import Course, Module
from app.models.enrollment import Enrollment

__all__ = [
    "User",
    "UserRole",
    "Profile",
    "Course",
    "Module",
    "Enrollment",
]
