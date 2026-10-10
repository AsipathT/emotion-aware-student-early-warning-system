"""
backend/app/schemas/consent.py

Feature 6: Consent and ethics notice Pydantic schemas.
Covers notices, user decisions (accepted, declined, withdrawn),
and consent history audit records.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ConsentDecision(str, Enum):
    """Possible consent decision statuses."""
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class ConsentNotice(BaseModel):
    """Published consent notice document."""
    id: Optional[str] = Field(default=None, description="Document ID")
    version: int = Field(..., description="Monotonically increasing version number")
    text: str = Field(..., description="Full text of the ethics and data usage notice")
    effective_from: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when notice took effect",
    )
    is_active: bool = Field(default=True, description="Whether this version is currently active")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ConsentNoticeCreate(BaseModel):
    """Admin payload to publish a new notice version."""
    text: str = Field(
        ...,
        min_length=10,
        description="Full text of the ethics and data usage notice",
        examples=[
            "To help us notice when students may need support, this LMS records how you use it..."
        ],
    )


class ConsentRecord(BaseModel):
    """Immutable audit entry recording a student's consent decision."""
    id: Optional[str] = Field(default=None, description="Consent record UUID")
    pid: str = Field(..., description="Student Pseudonym ID (e.g. STU_a1b2c3d4)")
    notice_version: int = Field(..., description="The notice version consented or declined")
    decision: ConsentDecision = Field(..., description="Decision made (accepted, declined, withdrawn)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when decision was submitted",
    )
    ip_or_client: Optional[str] = Field(
        default=None,
        description="IP address or User-Agent string recorded for compliance",
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class ConsentDecisionRequest(BaseModel):
    """Payload to record an accept or decline decision."""
    decision: ConsentDecision = Field(
        ...,
        description="Decision: 'accepted' or 'declined'",
        examples=["accepted"],
    )


class ConsentStatusResponse(BaseModel):
    """Summary of student's current consent posture and active notice status."""
    has_consented: bool = Field(
        ...,
        description="True if student has accepted the currently active notice version",
    )
    latest_decision: Optional[ConsentDecision] = Field(
        default=None,
        description="Most recent recorded decision for the active notice version",
    )
    notice_version: Optional[int] = Field(
        default=None,
        description="Currently active notice version",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the most recent decision",
    )
    consent_required: bool = Field(
        default=False,
        description="True if student has never recorded a decision for the active notice version",
    )
    active_notice: Optional[ConsentNotice] = Field(
        default=None,
        description="The active notice content and metadata",
    )
    history: List[ConsentRecord] = Field(
        default_factory=list,
        description="Audit trail of student's previous decisions",
    )

    model_config = {"from_attributes": True}
