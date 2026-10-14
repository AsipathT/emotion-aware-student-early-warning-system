"""
backend/app/models/support_resource.py

Feature 38-C: Support Resource & Referral Library Model.
Defines learning resources, time-management guidance, and institutional referrals
that staff counsellors can share with students during intervention delivery.
Persisted in collection `support_resources`.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
import uuid

from pydantic import BaseModel, Field

COL_SUPPORT_RESOURCES = "support_resources"

RESOURCE_TYPE_RESOURCE = "resource"
RESOURCE_TYPE_GUIDANCE = "guidance"
RESOURCE_TYPE_REFERRAL = "referral"

ResourceType = Literal["resource", "guidance", "referral"]

VALID_RESOURCE_TYPES = [
    RESOURCE_TYPE_RESOURCE,
    RESOURCE_TYPE_GUIDANCE,
    RESOURCE_TYPE_REFERRAL,
]


class SupportResource(BaseModel):
    """
    Cataloged learning resource, study guide, or service referral.
    Stored in `support_resources`.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        alias="_id",
        description="Unique identifier for the support resource",
    )
    title: str = Field(..., max_length=120, description="Short resource title")
    description: str = Field(..., max_length=500, description="Brief resource overview or guidance instructions")
    resource_type: ResourceType = Field(..., description="Categorical resource type (resource, guidance, referral)")
    url: Optional[str] = Field(default=None, description="External learning material or web link (http/https)")
    contact_info: Optional[str] = Field(default=None, max_length=200, description="Service point contact details, email, or office location")
    intervention_types: List[str] = Field(
        default_factory=list,
        description="Associated canonical intervention types (e.g., additional_learning_resources, time_management_guidance)",
    )
    is_active: bool = Field(default=True, description="Whether the resource is active and shareable")
    created_by: str = Field(..., description="User ID of staff creator")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
