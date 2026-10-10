"""
backend/tests/test_contract.py

Comprehensive test suite verifying Feature 24 (Shared JSON schema and versioning):
1. Every valid fixture passes; every invalid fixture fails and names the field.
2. Semantic versioning: unknown major -> 422; higher minor with extra field -> accepted;
   same minor with unknown field -> rejected (extra="forbid").
3. Boundary & unit constraints: Scores (0.0-1.0), enum values, ranks consecutive 1..N,
   modality contributions summing to 1.0 (+- 0.01).
4. Privacy safety nets:
   - Inspection walks all contract models ensuring no forbidden fields
     (student_id, registration_id, name, email, raw_text) exist.
   - PID validator adheres to Feature 5 format.
   - Emails and IT######## IDs in text fields are rejected without echoing values.
   - Naive datetimes are strictly rejected.
5. Envelope pagination constraints (page_size <= 500).
6. GET /api/v1/contract read-only endpoint and OpenAPI schema generation.
"""

import copy
import inspect
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.contract_validation import validated_envelope
from app.core.contract_version import (
    CONTRACT_VERSION,
    SUPPORTED_MAJORS,
    check_inbound_version,
    make_lenient_model,
    parse_version,
)
from app.core.privacy import is_valid_pid
from app.core.security import create_access_token
from app.main import app
from app.models.user import UserRole
from app.schemas.contract.common import (
    FORBIDDEN_FIELDS,
    DistressClass,
    Envelope,
    RiskTier,
    SourceType,
    TrajectoryLabel,
)
from app.schemas.contract.v1 import (
    AcademicRecord,
    AffectiveWeeklyVector,
    BehaviorWeeklyRecord,
    EngagementTrajectory,
    InterventionOutcome,
    InterventionRecommendation,
    RiskAssessment,
    TextMessageRecord,
    V1_CONTRACT_MODELS,
)
from tests.fixtures.contract import (
    ALL_VALID_FIXTURES,
    INVALID_FIXTURES,
    VALID_RISK_ASSESSMENT_ENVELOPE,
    VALID_TEXT_MESSAGE_ENVELOPE,
)

client = TestClient(app)


# ── Test 1: All Valid Fixtures Pass Cleanly ───────────────────────────────────

@pytest.mark.parametrize("model_cls", V1_CONTRACT_MODELS)
def test_valid_fixtures_pass(model_cls):
    model_name = model_cls.__name__
    fixture = ALL_VALID_FIXTURES[model_name]
    
    # Validate raw data item
    item = model_cls.model_validate(fixture["data"])
    assert item is not None

    # Validate full envelope
    envelope = Envelope[model_cls].model_validate(fixture)
    assert envelope.schema_version == "1.0"
    assert envelope.source is not None
    assert envelope.request_id == fixture["request_id"]


# ── Test 2: All Invalid Fixtures Fail and Name the Field ──────────────────────

@pytest.mark.parametrize("model_cls", V1_CONTRACT_MODELS)
def test_invalid_fixtures_fail_with_field_name(model_cls):
    model_name = model_cls.__name__
    invalid_cases = INVALID_FIXTURES[model_name]

    for desc, invalid_envelope, expected_field in invalid_cases:
        with pytest.raises(ValidationError) as exc_info:
            Envelope[model_cls].model_validate(invalid_envelope)

        error_str = str(exc_info.value).lower()
        assert expected_field.lower() in error_str, (
            f"Expected field '{expected_field}' in error for case '{desc}' on {model_name}.\n"
            f"Actual error: {error_str}"
        )


# ── Test 3: Contract Semantic Versioning Rules ────────────────────────────────

def test_parse_version():
    assert parse_version("1.0") == (1, 0)
    assert parse_version("2.14") == (2, 14)

    with pytest.raises(ValueError):
        parse_version("1")
    with pytest.raises(ValueError):
        parse_version("v1.0")
    with pytest.raises(ValueError):
        parse_version("1.0.0")


def test_version_compatibility_checks():
    # 1. Exact match supported version (1.0)
    res = check_inbound_version("1.0")
    assert res.major == 1
    assert res.minor == 0
    assert res.is_higher_minor is False

    # 2. Higher minor version (1.1, 1.5)
    res_higher = check_inbound_version("1.2")
    assert res_higher.major == 1
    assert res_higher.minor == 2
    assert res_higher.is_higher_minor is True

    # 3. Unsupported major version (2.0)
    with pytest.raises(HTTPException) as exc:
        check_inbound_version("2.0")
    assert exc.value.status_code == 422
    assert "Unsupported contract schema major version '2'" in str(exc.value.detail)


def test_higher_minor_accepts_extra_fields():
    """Higher minor (1.1) should ignore unexpected optional fields."""
    payload_higher_minor = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE)
    payload_higher_minor["schema_version"] = "1.1"
    payload_higher_minor["data"]["new_optional_feature_score"] = 0.95
    payload_higher_minor["extra_envelope_meta"] = "experimental"

    # Strict model rejects
    with pytest.raises(ValidationError):
        TextMessageRecord.model_validate(payload_higher_minor["data"])

    # Lenient model accepts and ignores
    lenient_model = make_lenient_model(TextMessageRecord)
    validated = lenient_model.model_validate(payload_higher_minor["data"])
    assert validated.message_id == "msg-001"
    assert not hasattr(validated, "new_optional_feature_score")


def test_same_minor_strictly_rejects_extra_fields():
    """Same minor (1.0) must strictly forbid unexpected fields."""
    payload = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE)
    payload["data"]["unexpected_field"] = "bad"

    with pytest.raises(ValidationError) as exc:
        TextMessageRecord.model_validate(payload["data"])
    assert "extra_forbidden" in str(exc.value)


# ── Test 4: Forbidden Identity Fields Denylist Check ──────────────────────────

def test_no_contract_model_contains_forbidden_fields():
    """
    Reflective check walking every v1 contract model.
    No model may define fields named student_id, registration_id, name, email, or raw_text.
    """
    for model_cls in V1_CONTRACT_MODELS:
        for field_name in model_cls.model_fields.keys():
            assert field_name.lower() not in FORBIDDEN_FIELDS, (
                f"Model '{model_cls.__name__}' defines forbidden PII field '{field_name}'! "
                "Must never allow identifying student data across component boundaries."
            )


# ── Test 5: PID Validation Adheres to Feature 5 ───────────────────────────────

def test_pid_validation():
    # Valid PIDs matching ^STU_[0-9a-fA-F]{8}$
    assert is_valid_pid("STU_cdbe990a") is True
    assert is_valid_pid("STU_1234abcd") is True
    assert is_valid_pid("STU_A1B2C3D4") is True

    # Invalid PIDs
    assert is_valid_pid("IT12345678") is False  # Institutional student ID
    assert is_valid_pid("STU_123") is False        # Too short
    assert is_valid_pid("STU_123456789") is False  # Too long
    assert is_valid_pid("STU_zzzzzzzz") is False   # Non-hex characters
    assert is_valid_pid("") is False
    assert is_valid_pid(None) is False


# ── Test 6: Text PII Safety Net (Email & Registration ID) ─────────────────────

def test_text_pii_safety_net_does_not_echo_values():
    bad_payload = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE["data"])
    bad_payload["clean_text"] = "Reach student at confidential_test@uni.edu immediately."

    with pytest.raises(ValidationError) as exc_info:
        TextMessageRecord.model_validate(bad_payload)

    err = exc_info.value.errors()[0]
    assert "email address detected" in err["msg"]
    # Ensure submitted email address is NOT echoed in the validator message
    assert "confidential_test@uni.edu" not in err["msg"]

    # Test registration ID pattern
    bad_payload["clean_text"] = "Collaborated on lab task with IT20184422."
    with pytest.raises(ValidationError) as exc_info:
        TextMessageRecord.model_validate(bad_payload)

    err = exc_info.value.errors()[0]
    assert "registration ID pattern IT######## detected" in err["msg"]
    assert "IT20184422" not in err["msg"]

    # Test via API endpoint: HTTP 422 JSON response must NEVER echo the offending text
    envelope_with_pii = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE)
    envelope_with_pii["data"]["clean_text"] = "Reach out to student at leak_test@lms.edu right away."
    resp = client.post("/api/v1/contract/example/text-message", json=envelope_with_pii)
    assert resp.status_code == 422
    assert "leak_test@lms.edu" not in resp.text
    assert "email address detected" in resp.text


# ── Test 7: Naive Datetimes Are Strictly Rejected ─────────────────────────────

def test_naive_datetime_rejected():
    bad_data = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE["data"])
    bad_data["timestamp"] = "2026-10-10T12:00:00"  # Naive datetime missing offset

    with pytest.raises(ValidationError) as exc:
        TextMessageRecord.model_validate(bad_data)
    assert "timezone-aware (utc)" in str(exc.value).lower()


# ── Test 8: Specific Business & Scientific Constraint Validations ─────────────

def test_risk_modality_contributions_sum_constraint():
    bad_risk = copy.deepcopy(VALID_RISK_ASSESSMENT_ENVELOPE["data"])
    # Sums to 0.70 instead of 1.00
    bad_risk["modality_contributions"] = {
        "affective": 0.30,
        "behavioral": 0.20,
        "academic": 0.20,
    }
    with pytest.raises(ValidationError) as exc:
        RiskAssessment.model_validate(bad_risk)
    assert "modality contributions must sum to 1.0" in str(exc.value).lower()


def test_intervention_candidate_ranks_consecutive():
    from tests.fixtures.contract import VALID_INTERVENTION_REC_ENVELOPE
    bad_rec = copy.deepcopy(VALID_INTERVENTION_REC_ENVELOPE["data"])
    # Ranks [1, 3] are not consecutive
    bad_rec["candidates"][1]["rank"] = 3
    with pytest.raises(ValidationError) as exc:
        InterventionRecommendation.model_validate(bad_rec)
    assert "must be unique and consecutive" in str(exc.value).lower()


def test_envelope_page_size_max_500():
    envelope_data = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE)
    envelope_data["page"] = 1
    envelope_data["page_size"] = 501  # Exceeds max 500

    with pytest.raises(ValidationError) as exc:
        Envelope[TextMessageRecord].model_validate(envelope_data)
    assert "page_size" in str(exc.value)


# ── Test 9: Example Routes & API Validation ───────────────────────────────────

def test_get_contract_info_authenticated():
    from app.core.dependencies import get_current_user
    from app.models.user import User

    import uuid
    mock_user = User(
        id=uuid.uuid4(),
        email="tester@lms.edu",
        hashed_password="hashed_pw_test",
        full_name="Contract Tester",
        role=UserRole.LECTURER,
        is_active=True,
        is_verified=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.get("/api/v1/contract")
        assert response.status_code == 200
        data = response.json()
        assert data["contract_version"] == CONTRACT_VERSION
        assert 1 in data["supported_majors"]
        assert "Envelope" in data["schemas"]
        assert "TextMessageRecord" in data["schemas"]
        assert "RiskAssessment" in data["schemas"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_contract_info_unauthenticated():
    response = client.get("/api/v1/contract")
    assert response.status_code == 401 or response.status_code == 403


def test_post_example_text_message_route():
    # Valid payload
    response = client.post(
        "/api/v1/contract/example/text-message",
        json=VALID_TEXT_MESSAGE_ENVELOPE,
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "valid"
    assert res_data["received_version"] == "1.0"
    assert res_data["count"] == 1

    # Invalid payload (unknown major version)
    invalid_ver_payload = copy.deepcopy(VALID_TEXT_MESSAGE_ENVELOPE)
    invalid_ver_payload["schema_version"] = "3.0"
    response_invalid = client.post(
        "/api/v1/contract/example/text-message",
        json=invalid_ver_payload,
    )
    assert response_invalid.status_code == 422


def test_openapi_schema_contains_contract_routes():
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})
    assert "/api/v1/contract" in paths
    assert "/api/v1/contract/example/text-message" in paths
    assert "/api/v1/contract/example/risk-assessment" in paths
