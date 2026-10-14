"""
backend/app/schemas/staff_resources.py

Feature 38-C: Staff Support Resource & Referral Schemas.
Provides request and response validation for resource catalog management,
URL scheme verification (http/https only), and intervention resource sharing.
"""

from datetime import datetime
from typing import List, Literal, Optional
import urllib.parse

from pydantic import BaseModel, Field, field_validator, model_validator


def validate_http_url(v: Optional[str]) -> Optional[str]:
    """
    Validates that a string is a valid HTTP or HTTPS URL.
    Rejects dangerous/unsupported schemes such as 'javascript:' or 'ftp:'.
    """
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        return None

    parsed = urllib.parse.urlparse(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            "URL must use an 'http' or 'https' protocol with a valid network domain (e.g. https://example.com/guide)."
        )
    return cleaned


class ResourceCreate(BaseModel):
    """Payload for cataloging a new support resource, guidance note, or referral."""
    title: str = Field(..., min_length=1, max_length=120, description="Resource title (1-120 chars)")
    description: str = Field(..., min_length=1, max_length=500, description="Overview or instructions (1-500 chars)")
    resource_type: Literal["resource", "guidance", "referral"] = Field(
        ...,
        description="Categorical resource classification: resource | guidance | referral",
    )
    url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Direct web link to materials (http/https only)",
    )
    contact_info: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Physical location, email, or telephone for service point referrals",
    )
    intervention_types: List[str] = Field(
        default_factory=list,
        description="Canonical intervention types this resource relates to",
    )
    is_active: bool = Field(default=True, description="Whether resource is active and shareable")

    @field_validator("url")
    @classmethod
    def check_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_url(v)

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or blank whitespace.")
        return s

    @model_validator(mode="after")
    def check_url_or_contact_info(self):
        url_val = self.url.strip() if self.url else None
        contact_val = self.contact_info.strip() if self.contact_info else None
        if not url_val and not contact_val:
            raise ValueError("At least one of 'url' or 'contact_info' is required.")
        return self


class ResourceUpdate(BaseModel):
    """Payload for modifying an existing support resource or toggling active status."""
    title: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    resource_type: Optional[Literal["resource", "guidance", "referral"]] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    contact_info: Optional[str] = Field(default=None, max_length=200)
    intervention_types: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def check_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            return validate_http_url(v)
        return None

    @field_validator("title", "description")
    @classmethod
    def strip_text_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Field cannot be empty or blank whitespace.")
            return s
        return v


class ResourceResponse(BaseModel):
    """Public staff representation of a support resource."""
    id: str
    title: str
    description: str
    resource_type: str
    url: Optional[str] = None
    contact_info: Optional[str] = None
    intervention_types: List[str] = []
    is_active: bool = True
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }


class ResourceListResponse(BaseModel):
    """Paginated or filtered list of support resources."""
    items: List[ResourceResponse]
    total_count: int


class ShareResourceRequest(BaseModel):
    """Payload for sharing a resource with a student intervention."""
    resource_id: str = Field(..., min_length=1, description="ID of active resource in support_resources")
    message: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Optional personal counselor guidance note (max 300 chars)",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            return s if s else None
        return None


class SharedResourceItemDetail(BaseModel):
    """Detail of a resource shared with a specific intervention."""
    resource_id: str
    title: str
    description: str
    resource_type: str
    url: Optional[str] = None
    contact_info: Optional[str] = None
    shared_at: datetime
    shared_by: str
    viewed_at: Optional[datetime] = None
    message: Optional[str] = None


class SharedResourceListResponse(BaseModel):
    """List of shared resources for an intervention."""
    items: List[SharedResourceItemDetail]
    total_count: int
