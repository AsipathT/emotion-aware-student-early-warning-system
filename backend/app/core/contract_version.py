"""
backend/app/core/contract_version.py

Feature 24: Contract Versioning and Semantic Compatibility Rules.

════════════════════════════════════════════════════════════════════════════════
NAMING NOTE & ARCHITECTURAL DISTINCTION
════════════════════════════════════════════════════════════════════════════════
Existing stored documents (such as MongoDB audit logs or consent records) use an
integer `schema_version` (e.g. 1, 2) for internal DATABASE storage versioning.

The data contract version defined in this module (`CONTRACT_VERSION = "1.0"`) is
a fundamentally different entity:
- It governs inter-system communication between the LMS core and the four ML
  subsystems (C1, C2, C3, C4).
- In Python code, it is represented as `CONTRACT_VERSION` and managed via this
  `contract_version` helper module.
- In JSON transmission envelopes, it is serialized in the `schema_version` field
  as a semantic "major.minor" string (e.g. "1.0", "1.1").

════════════════════════════════════════════════════════════════════════════════
SEMANTIC VERSIONING EVOLUTION RULES
════════════════════════════════════════════════════════════════════════════════
1. MINOR VERSION INCREMENT (e.g. 1.0 -> 1.1):
   - Backwards-compatible additions ONLY:
     * Additive optional fields with safe defaults.
     * New ignorable metadata or new enum variants that do not break consumers.
   - Consumers (LMS or ML component) running on minor version 1.0 receiving a 1.1
     payload will accept the payload and gracefully IGNORE any unknown optional
     fields (`extra="ignore"` for higher minor).
   - Payloads arriving at the current or lower minor (e.g. 1.0) strictly reject
     unexpected fields (`extra="forbid"`).

2. MAJOR VERSION INCREMENT (e.g. 1.x -> 2.0):
   - Breaking contract modifications:
     * Renaming or removing existing fields.
     * Altering data types, ranges, or mathematical units (e.g. changing 0-100% to 0.0-1.0).
     * Semantic or behavioral redefinitions of fields.
   - Unknown major versions are rejected immediately with HTTP 422.
   - During cross-team migration transitions, both current and immediately previous
     major versions are maintained concurrently.
"""

import re
from typing import Any, Dict, NamedTuple, Set, Tuple, get_args, get_origin
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, create_model

# Current active contract version and supported major versions
CONTRACT_VERSION: str = "1.0"
SUPPORTED_MAJORS: Set[int] = {1}

VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)$")


class VersionCheckResult(NamedTuple):
    major: int
    minor: int
    is_higher_minor: bool
    version_str: str


def parse_version(version_str: str) -> Tuple[int, int]:
    """
    Parses a contract schema version string formatted as 'major.minor'.
    Returns (major, minor) tuple of integers.

    Raises:
        ValueError: If version_str is not in the strict 'major.minor' format.
    """
    if not isinstance(version_str, str):
        raise ValueError(
            f"Invalid contract version type: expected str, got {type(version_str).__name__}."
        )

    match = VERSION_PATTERN.match(version_str.strip())
    if not match:
        raise ValueError(
            f"Invalid contract schema version format '{version_str}'. "
            "Must be formatted as 'major.minor' integers (e.g. '1.0')."
        )

    return int(match.group(1)), int(match.group(2))


def check_inbound_version(version_str: str) -> VersionCheckResult:
    """
    Validates an incoming contract envelope's schema_version string.

    Rules:
    - Must be a valid 'major.minor' string.
    - Major version must exist in SUPPORTED_MAJORS; otherwise raises HTTP 422.
    - Minor version is compared to active CONTRACT_VERSION:
      * Equal or lower minor: accepted in strict mode (extra='forbid').
      * Higher minor: accepted in forward-compatible lenient mode (extra='ignore').

    Returns:
        VersionCheckResult containing major, minor, and is_higher_minor flag.
    """
    try:
        major, minor = parse_version(version_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "loc": ["body", "schema_version"],
                    "msg": str(exc),
                    "type": "value_error.contract_version",
                }
            ],
        )

    if major not in SUPPORTED_MAJORS:
        supported_str = ", ".join(str(m) for m in sorted(SUPPORTED_MAJORS))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "loc": ["body", "schema_version"],
                    "msg": (
                        f"Unsupported contract schema major version '{major}'. "
                        f"Supported major versions: [{supported_str}]."
                    ),
                    "type": "value_error.unsupported_major_version",
                }
            ],
        )

    current_major, current_minor = parse_version(CONTRACT_VERSION)
    is_higher = (major == current_major and minor > current_minor)

    return VersionCheckResult(
        major=major,
        minor=minor,
        is_higher_minor=is_higher,
        version_str=version_str,
    )


# ── Forward-Compatibility Lenient Model Builder ───────────────────────────────

_LENIENT_CACHE: Dict[type, type] = {}


def make_lenient_model(model_cls: type[BaseModel]) -> type[BaseModel]:
    """
    Dynamically generates or retrieves a forward-compatible copy of a Pydantic model
    with `extra='ignore'`, applied recursively to all nested BaseModel fields.

    Approach:
    When a contract payload arrives with a higher minor version (e.g. '1.1' when current is '1.0'),
    unknown optional fields introduced by newer producers must be gracefully ignored rather
    than rejected with validation errors.
    This function clones the model definition with `extra='ignore'` while preserving
    all field types, constraints, and custom validators.
    """
    if model_cls in _LENIENT_CACHE:
        return _LENIENT_CACHE[model_cls]

    def _transform_type(ann: Any) -> Any:
        origin = get_origin(ann)
        if origin is not None:
            args = get_args(ann)
            transformed = tuple(_transform_type(a) for a in args)
            return origin[transformed]
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            return make_lenient_model(ann)
        return ann

    field_definitions: Dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        field_definitions[name] = (_transform_type(field_info.annotation), field_info)

    lenient_cls = create_model(
        f"Lenient_{model_cls.__name__}",
        __base__=model_cls,
        __config__=ConfigDict(extra="ignore", str_strip_whitespace=True),
        **field_definitions,
    )

    _LENIENT_CACHE[model_cls] = lenient_cls
    return lenient_cls
