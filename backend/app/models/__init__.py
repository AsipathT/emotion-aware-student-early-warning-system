# models package – import all model modules here so Alembic discovers them.
from app.models.user import User          # noqa: F401
from app.models.profile import Profile    # noqa: F401
from app.models.course import Course, Module  # noqa: F401
from app.models.enrollment import Enrollment  # noqa: F401
