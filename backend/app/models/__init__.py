# models package – import all model modules here so Alembic discovers them.
from app.models.user import User          # noqa: F401
from app.models.profile import Profile    # noqa: F401
from app.models.course import Course, Module  # noqa: F401
from app.models.enrollment import Enrollment  # noqa: F401
from app.models.assessment import Assignment, AssignmentSubmission, Quiz, QuizQuestion, QuizOption, QuizAttempt, QuizAnswer  # noqa: F401
from app.models.gradebook import GradebookEntry  # noqa: F401
from app.models.attendance import AttendanceSession, AttendanceRecord  # noqa: F401
from app.models.behaviour import UserSession, ClickEvent  # noqa: F401
from app.models.analytics import WeeklyFeature, RiskScore, TrajectoryLabel, SyntheticGroundTruth, AffectWeekly  # noqa: F401
