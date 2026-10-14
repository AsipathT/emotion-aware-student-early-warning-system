"""
backend/tests/test_feature38c_resources.py

Feature 38-C: Unit tests for URL validation, resource schemas, and student-facing models.
NOTE: As per standing rules, these tests are written but NOT run during pairing execution.
"""

import pytest
from pydantic import ValidationError

from app.schemas.staff_resources import (
    ResourceCreate,
    ResourceUpdate,
    ShareResourceRequest,
    validate_http_url,
)
from app.schemas.support_student import (
    MarkResourceViewedResponse,
    StudentSharedResourceItem,
)


def test_validate_http_url_valid_schemes():
    """Verifies that HTTP and HTTPS URLs with valid domains pass validation."""
    assert validate_http_url("http://example.com") == "http://example.com"
    assert (
        validate_http_url("https://learning.university.edu/course/101")
        == "https://learning.university.edu/course/101"
    )
    assert validate_http_url("  https://docs.org/guide  ") == "https://docs.org/guide"
    assert validate_http_url(None) is None
    assert validate_http_url("") is None


def test_validate_http_url_rejects_dangerous_or_invalid_schemes():
    """Verifies that dangerous or unsupported protocols raise ValueError (yielding 422)."""
    with pytest.raises(ValueError, match="URL must use an 'http' or 'https' protocol"):
        validate_http_url("javascript:alert(1)")

    with pytest.raises(ValueError, match="URL must use an 'http' or 'https' protocol"):
        validate_http_url("ftp://files.example.com/handout.pdf")

    with pytest.raises(ValueError, match="URL must use an 'http' or 'https' protocol"):
        validate_http_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="URL must use an 'http' or 'https' protocol"):
        validate_http_url("data:text/html;base64,PHNjcmlwdD4=")

    with pytest.raises(ValueError, match="URL must use an 'http' or 'https' protocol"):
        validate_http_url("not-a-valid-url")


def test_resource_create_requires_url_or_contact_info():
    """Verifies that at least one of url or contact_info is mandatory."""
    # Providing URL only -> Valid
    rc1 = ResourceCreate(
        title="Math Revision Guide",
        description="Curated formative exercises",
        resource_type="resource",
        url="https://math.example.com",
    )
    assert rc1.url == "https://math.example.com"
    assert rc1.contact_info is None

    # Providing Contact info only -> Valid
    rc2 = ResourceCreate(
        title="Campus Disability Hub",
        description="Physical referral service point",
        resource_type="referral",
        contact_info="Student Wellbeing Center, Room 102",
    )
    assert rc2.contact_info == "Student Wellbeing Center, Room 102"
    assert rc2.url is None

    # Providing neither -> ValidationError
    with pytest.raises(ValidationError, match="At least one of 'url' or 'contact_info' is required"):
        ResourceCreate(
            title="Empty Contact Resource",
            description="Lacks destination information",
            resource_type="guidance",
        )


def test_resource_create_rejects_empty_blank_title_or_description():
    """Verifies that whitespace-only titles or descriptions are rejected."""
    with pytest.raises(ValidationError, match="Field cannot be empty"):
        ResourceCreate(
            title="   ",
            description="Valid description",
            resource_type="resource",
            url="https://example.com",
        )

    with pytest.raises(ValidationError, match="Field cannot be empty"):
        ResourceCreate(
            title="Valid Title",
            description="   ",
            resource_type="resource",
            url="https://example.com",
        )


def test_share_resource_request_message_constraint():
    """Verifies message constraint on resource sharing."""
    req = ShareResourceRequest(
        resource_id="res-1234",
        message="  Take a look at module 3 study guide  ",
    )
    assert req.message == "Take a look at module 3 study guide"

    # Excessive length > 300 chars
    with pytest.raises(ValidationError):
        ShareResourceRequest(
            resource_id="res-1234",
            message="X" * 301,
        )


def test_student_shared_resource_item_schema():
    """Verifies student-facing resource item schema without exposing staff clinical notes."""
    item = StudentSharedResourceItem(
        id="res-456",
        resource_id="res-456",
        title="Time Management Workshop",
        description="Self-paced time management guidance module",
        resource_type="guidance",
        type="guidance",
        url="https://timemanagement.example.com",
        contact_info=None,
        message="Recommended for study schedule planning",
        shared_at=None,
        viewed=True,
        viewed_at=None,
    )
    assert item.title == "Time Management Workshop"
    assert item.viewed is True
    assert not hasattr(item, "notes")
    assert not hasattr(item, "pid")
    assert not hasattr(item, "recommendation_id")
