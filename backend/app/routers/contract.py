"""
backend/app/routers/contract.py

Feature 24: Data Contract Information and Validation Example Endpoints.
Provides:
- GET /api/v1/contract: Read-only endpoint returning active CONTRACT_VERSION,
  supported major versions, and registered schema names (authenticated users only).
- POST /api/v1/contract/example/text-message: Test route exercising validated_envelope
  with TextMessageRecord.
- POST /api/v1/contract/example/risk-assessment: Test route exercising validated_envelope
  with RiskAssessment.
"""

from typing import Any, List
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.core.contract_validation import validated_envelope
from app.core.contract_version import CONTRACT_VERSION, SUPPORTED_MAJORS
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.contract.common import Envelope
from app.schemas.contract.v1 import (
    RiskAssessment,
    TextMessageRecord,
    V1_CONTRACT_MODELS,
)

router = APIRouter(prefix="/api/v1/contract", tags=["contract"])


class ContractInfoResponse(BaseModel):
    """Metadata response describing active data contract specifications."""
    contract_version: str = Field(
        ...,
        description="Active contract version (major.minor)",
        examples=["1.0"],
    )
    supported_majors: List[int] = Field(
        ...,
        description="List of supported major version numbers",
        examples=[[1]],
    )
    schemas: List[str] = Field(
        ...,
        description="List of registered data contract model names",
    )


class ValidationExampleResponse(BaseModel):
    """Response returned by example validation endpoints in test environments."""
    status: str = "valid"
    received_version: str
    source: str
    request_id: str
    is_list: bool
    count: int


@router.get(
    "",
    response_model=ContractInfoResponse,
    summary="Get active data contract metadata",
    description=(
        "Returns active CONTRACT_VERSION, supported major versions, and registered "
        "v1 contract model definitions. Accessible to all authenticated users."
    ),
)
async def get_contract_info(
    current_user: User = Depends(get_current_user),
) -> ContractInfoResponse:
    """Read-only metadata endpoint exposing active contract specifications."""
    schema_names = ["Envelope"] + sorted([m.__name__ for m in V1_CONTRACT_MODELS])
    return ContractInfoResponse(
        contract_version=CONTRACT_VERSION,
        supported_majors=sorted(list(SUPPORTED_MAJORS)),
        schemas=schema_names,
    )


@router.post(
    "/example/text-message",
    response_model=ValidationExampleResponse,
    status_code=status.HTTP_200_OK,
    summary="Example route validating TextMessageRecord envelope (used in tests)",
    description="Validates an inbound envelope payload containing TextMessageRecord item(s).",
)
async def validate_text_message_example(
    envelope: Envelope[Any] = Depends(validated_envelope(TextMessageRecord)),
) -> ValidationExampleResponse:
    is_list = isinstance(envelope.data, list)
    count = len(envelope.data) if is_list else 1
    return ValidationExampleResponse(
        status="valid",
        received_version=envelope.schema_version,
        source=envelope.source.value,
        request_id=envelope.request_id,
        is_list=is_list,
        count=count,
    )


@router.post(
    "/example/risk-assessment",
    response_model=ValidationExampleResponse,
    status_code=status.HTTP_200_OK,
    summary="Example route validating RiskAssessment envelope (used in tests)",
    description="Validates an inbound envelope payload containing RiskAssessment item(s).",
)
async def validate_risk_assessment_example(
    envelope: Envelope[Any] = Depends(validated_envelope(RiskAssessment)),
) -> ValidationExampleResponse:
    is_list = isinstance(envelope.data, list)
    count = len(envelope.data) if is_list else 1
    return ValidationExampleResponse(
        status="valid",
        received_version=envelope.schema_version,
        source=envelope.source.value,
        request_id=envelope.request_id,
        is_list=is_list,
        count=count,
    )
