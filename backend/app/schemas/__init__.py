# schemas package
from app.schemas.auth import (  # noqa: F401
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.profile import (  # noqa: F401
    ProfileResponse,
    ProfileUpdate,
    UserDetailResponse,
    UserMeResponse,
)
from app.schemas.course import (  # noqa: F401
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    ModuleCreate,
    ModuleResponse,
)
from app.schemas.assessment import (  # noqa: F401
    AssignmentCreate, AssignmentUpdate, AssignmentResponse,
    AssignmentSubmissionCreate, AssignmentSubmissionGrade, AssignmentSubmissionResponse,
    QuizCreate, QuizUpdate, QuizResponse, QuizQuestionCreate, QuizQuestionResponse,
    QuizQuestionStudentResponse, QuizAnswerCreate, QuizAttemptResponse
)
from app.schemas.gradebook import GradebookEntryCreate, GradebookEntryResponse  # noqa: F401
from app.schemas.attendance import (  # noqa: F401
    AttendanceSessionCreate, AttendanceSessionResponse,
    AttendanceRecordCreate, AttendanceRecordResponse, BulkAttendanceMark
)
from app.schemas.behaviour import (  # noqa: F401
    UserSessionCreate, UserSessionUpdate, UserSessionResponse,
    ClickEventCreate, ClickEventResponse, BulkClickEventCreate
)
from app.schemas.analytics import (  # noqa: F401
    WeeklyFeatureResponse, RiskScoreResponse, TrajectoryLabelResponse,
    AffectWeeklyCreate, AffectWeeklyResponse, BulkAffectWeeklyCreate
)
