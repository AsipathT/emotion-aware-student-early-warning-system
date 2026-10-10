"""
backend/app/schemas/contract/common.py

Feature 24: Common types, enums, base models, and the generic contract envelope.
All contracts enforce strict validation, extra="forbid", UTC timezone awareness,
and total exclusion of student personally identifiable information (PII).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Generic, List, Optional, TypeVar, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.privacy import EMAIL_REGEX, REG_ID_REGEX, is_valid_pid


# ── Forbidden Field Names Denylist ────────────────────────────────────────────

FORBIDDEN_FIELDS = frozenset({
    "student_id",
    "registration_id",
    "name",
    "email",
    "raw_text",
})


# ── Text Sanitization & PII Safety Net ────────────────────────────────────────

def validate_clean_text(value: Any) -> str:
    """
    Validates that a string does not contain un-redacted email addresses or
    institutional registration IDs (IT followed by 8 digits).
    Never echoes offending values in exception messages for privacy.
    """
    if not isinstance(value, str):
        return value
    if EMAIL_REGEX.search(value):
        raise ValueError(
            "Text contains forbidden identifying information (email address detected). "
            "Raw value is omitted for privacy."
        )
    if REG_ID_REGEX.search(value):
        raise ValueError(
            "Text contains forbidden identifying information (registration ID pattern IT######## detected). "
            "Raw value is omitted for privacy."
        )
    return value


CleanText = Annotated[
    str,
    AfterValidator(validate_clean_text),
    Field(description="Scrubbed text safe from personal identifiers"),
]


# ── Custom Primitives ─────────────────────────────────────────────────────────

def validate_utc_datetime(dt: Any) -> datetime:
    """
    Ensures that datetime instances are timezone-aware and converted to UTC.
    Strictly rejects naive datetimes.
    """
    if not isinstance(dt, datetime):
        raise ValueError("Field must be a valid datetime instance.")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(
            "Datetime must be timezone-aware (UTC). Naive datetimes are strictly rejected."
        )
    return dt.astimezone(timezone.utc)


UtcDatetime = Annotated[
    datetime,
    AfterValidator(validate_utc_datetime),
    Field(description="UTC-aware timestamp (ISO 8601)"),
]


def validate_pid_value(pid_val: Any) -> str:
    """
    Validates that the pseudonym ID strictly matches the Feature 5 format:
    STU_ prefix followed by 8 hexadecimal characters.
    """
    if not isinstance(pid_val, str) or not is_valid_pid(pid_val):
        raise ValueError(
            "Invalid Pseudonym ID (PID). Must strictly adhere to Feature 5 format: "
            "STU_ followed by 8 hexadecimal characters (e.g. STU_a1b2c3d4)."
        )
    return pid_val.strip()


Pid = Annotated[
    str,
    Field(
        pattern=r"^STU_[0-9a-fA-F]{8}$",
        description="Feature 5 pseudonymized student identifier (e.g. STU_a1b2c3d4)",
    ),
    AfterValidator(validate_pid_value),
]

CourseId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        description="Course institutional identifier (e.g. CS101, SE4020)",
    ),
]

WeekIndex = Annotated[
    int,
    Field(
        ge=0,
        description="Academic term week index (zero-based: 0 = Week 1, 1 = Week 2, ...)",
    ),
]

Score01 = Annotated[
    float,
    Field(
        ge=0.0,
        le=1.0,
        description="Normalized metric score bounded between 0.0 and 1.0 inclusive",
    ),
]


# ── Shared Enums (Defined ONCE for all contracts) ─────────────────────────────

class SourceType(str, Enum):
    """Source medium where the LMS text interaction occurred."""
    FORUM = "forum"
    CHAT = "chat"
    JOURNAL = "journal"


class DistressClass(str, Enum):
    """Fine-grained student academic distress categories identified by C1."""
    EXAM_ANXIETY = "exam_anxiety"
    CONCEPTUAL_CONFUSION = "conceptual_confusion"
    ACADEMIC_HELPLESSNESS = "academic_helplessness"
    COURSE_FRUSTRATION = "course_frustration"
    MOTIVATION_EROSION = "motivation_erosion"


class TrajectoryLabel(str, Enum):
    """Longitudinal engagement pattern detected by C2."""
    STABLE = "stable"
    IMPROVING = "improving"
    DECLINING = "declining"
    VOLATILE = "volatile"


class RiskTier(str, Enum):
    """Multimodal dropout or disengagement risk classification produced by C3."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComponentSource(str, Enum):
    """Originating subsystem or ML component that generated the envelope."""
    LMS = "lms"
    C1 = "c1"
    C2 = "c2"
    C3 = "c3"
    C4 = "c4"


class Decision(str, Enum):
    """Staff decision recorded for an intervention recommendation."""
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


# ── Base Contract Model ───────────────────────────────────────────────────────

class ContractBaseModel(BaseModel):
    """
    Base class for all data contract payload models.
    Enforces:
    - Extra fields forbidden (`extra="forbid"`)
    - String whitespace stripped
    - Strict denylist check against student PII field names
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for field_name in cls.model_fields.keys():
            if field_name.lower() in FORBIDDEN_FIELDS:
                raise TypeError(
                    f"Contract model '{cls.__name__}' cannot define forbidden field '{field_name}'. "
                    f"Component boundaries must never transmit identifying student data."
                )


# ── Generic Contract Envelope ────────────────────────────────────────────────

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """
    Standardized transmission envelope wrapping all LMS <-> ML component payloads.
    Provides semantic contract versioning, origin tagging, correlation request IDs,
    and optional pagination metadata for batch queries.
    """
    schema_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+$",
        description="Semantic contract version formatted as 'major.minor' string (e.g. '1.0')",
    )
    generated_at: UtcDatetime = Field(
        ...,
        description="UTC timestamp recording when this envelope payload was assembled",
    )
    source: ComponentSource = Field(
        ...,
        description="Emitting subsystem identifier (lms, c1, c2, c3, c4)",
    )
    request_id: str = Field(
        ...,
        min_length=1,
        description="Unique correlation request identifier (matches X-Request-ID)",
    )
    data: Union[T, List[T]] = Field(
        ...,
        description="The strongly-typed payload entity or list of entities",
    )
    page: Optional[int] = Field(
        default=None,
        ge=1,
        description="Current 1-based page index for list responses",
    )
    page_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=500,
        description="Items per page for list responses (maximum 500)",
    )
    total: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total number of items across all pages for batch list queries",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )
