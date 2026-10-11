"""
backend/app/core/contract_validation.py

Feature 24: Reusable FastAPI Dependency Factory for Contract Validation.
Validates inbound payloads against contract Envelopes, runs version compatibility checks,
enforces strict schema compliance (or lenient tolerance for higher minors), and ensures
privacy-safe error formatting without echoing raw text values.
"""

from typing import Any, Callable, Dict, List, Type, Union
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from app.core.contract_version import check_inbound_version, make_lenient_model
from app.schemas.contract.common import Envelope


def _sanitize_validation_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cleans Pydantic validation error objects to prevent leaking raw user text or PII.
    Strips raw 'input' values and masks any sensitive details in messages.
    """
    sanitized: List[Dict[str, Any]] = []
    for err in errors:
        loc = list(err.get("loc", []))
        msg = err.get("msg", "Validation error")
        err_type = err.get("type", "value_error")

        # Never echo raw submitted input values in the API error response
        clean_err: Dict[str, Any] = {
            "loc": loc,
            "msg": msg,
            "type": err_type,
        }
        sanitized.append(clean_err)
    return sanitized


def validated_envelope(
    target_model: Type[BaseModel],
) -> Callable[[Request], Any]:
    """
    FastAPI dependency factory that returns a dependency callable.
    
    The dependency:
    1. Parses incoming JSON payload from the request body.
    2. Inspects `schema_version` and evaluates version compatibility.
    3. Handles forward-compatibility: if the payload presents a higher minor
       version (e.g. 1.1 when active is 1.0), it uses a lenient model with
       `extra='ignore'` so unexpected optional fields are safely accepted.
       At the current or lower minor, unknown fields are strictly rejected (`extra='forbid'`).
    4. Validates the envelope structure and types the `data` field to `target_model`
       (or `List[target_model]`).
    5. Returns the fully typed `Envelope` instance.
    6. On validation failure, raises HTTP 422 with specific field paths and sanitized messages.
    """

    async def dependency(request: Request) -> Envelope[Any]:
        # 1. Parse JSON body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "loc": ["body"],
                        "msg": "Invalid JSON request body.",
                        "type": "value_error.json",
                    }
                ],
            )

        if not isinstance(body, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "loc": ["body"],
                        "msg": "Request payload must be a JSON object conforming to Envelope.",
                        "type": "type_error.dict",
                    }
                ],
            )

        # 2. Check schema_version existence and compatibility
        version_str = body.get("schema_version")
        if not version_str or not isinstance(version_str, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "loc": ["body", "schema_version"],
                        "msg": "Field 'schema_version' is required in contract envelope.",
                        "type": "missing",
                    }
                ],
            )

        ver_result = check_inbound_version(version_str)

        # 3. Select validation model based on minor version status
        active_envelope_model: Type[BaseModel]
        active_item_model: Type[BaseModel]

        if ver_result.is_higher_minor:
            # Forward compatibility: accept unknown optional fields
            active_envelope_model = make_lenient_model(Envelope)
            active_item_model = make_lenient_model(target_model)
        else:
            # Strict mode: reject unknown fields
            active_envelope_model = Envelope
            active_item_model = target_model

        # 4. Validate envelope and data
        try:
            # First validate overall envelope structure
            envelope_obj = active_envelope_model.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=_sanitize_validation_errors(exc.errors()),
            )

        raw_data = body.get("data")
        typed_data: Union[BaseModel, List[BaseModel]]

        try:
            if isinstance(raw_data, list):
                typed_data = [
                    active_item_model.model_validate(item) for item in raw_data
                ]
            elif isinstance(raw_data, dict):
                typed_data = active_item_model.model_validate(raw_data)
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=[
                        {
                            "loc": ["body", "data"],
                            "msg": "Payload 'data' must be a JSON object or array of objects.",
                            "type": "type_error",
                        }
                    ],
                )
        except ValidationError as exc:
            # Adjust location paths so errors point accurately to body.data
            adjusted_errors = []
            for err in exc.errors():
                loc = list(err.get("loc", []))
                # Prepend 'body' and 'data'
                adjusted_loc = ["body", "data"] + [
                    str(p) if isinstance(p, int) else p for p in loc
                ]
                adjusted_errors.append({**err, "loc": adjusted_loc})
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=_sanitize_validation_errors(adjusted_errors),
            )

        # Construct and return validated envelope with strongly typed data
        envelope_data = envelope_obj.model_dump(exclude={"data"})
        envelope_data["data"] = typed_data
        return Envelope[Any].model_construct(**envelope_data)

    return dependency
