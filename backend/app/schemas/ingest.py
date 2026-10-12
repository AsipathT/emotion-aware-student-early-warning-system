"""
backend/app/schemas/ingest.py

Feature 23: Component Output Ingestion Schemas.
Standardized response payload structure returned by all /api/v1/ingest endpoints.
"""

from typing import List
from pydantic import BaseModel, Field


class RejectedRecordItem(BaseModel):
    """Details of a record rejected during Stage 2 business validation."""
    index: int = Field(..., description="0-based index of the rejected item in submitted batch")
    pid: str = Field(..., description="Pseudonym ID of the rejected student")
    reason_code: str = Field(..., description="Machine-readable rejection reason code")


class IngestResponse(BaseModel):
    """
    Standard response payload for all ML component output ingestion endpoints.
    Always returns HTTP 200 once request envelope is validated and processed,
    reporting detailed counts and rejection reason codes without echoing submitted text.
    """
    run_id: str = Field(..., description="Unique ingestion batch execution identifier")
    schema_version: str = Field(..., description="Contract schema version echoed from envelope")
    dry_run: bool = Field(default=False, description="Whether execution was a dry run without database writes")
    received: int = Field(..., description="Total records received in payload")
    accepted: int = Field(..., description="Total records passing Stage 2 validation")
    rejected: int = Field(..., description="Total records rejected at Stage 2")
    created: int = Field(..., description="Count of new documents created (or would be created)")
    updated: int = Field(..., description="Count of existing documents updated/replaced (or would be updated)")
    rejected_records: List[RejectedRecordItem] = Field(
        default_factory=list,
        description="List of rejected records with indices and reason codes",
    )
