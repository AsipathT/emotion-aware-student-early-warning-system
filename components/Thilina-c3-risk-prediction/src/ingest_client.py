"""
components/Thilina-c3-risk-prediction/src/ingest_client.py

Client for sending C3 Multimodal Risk Predictions to the LMS Ingestion API.
Complies with contracts/v1/RiskAssessment.json and Feature 23 Ingestion Specification:
  - URL: POST {PLATFORM_URL}/api/v1/ingest/risk
  - Header: X-Component-Key: {C3_COMPONENT_KEY}
  - Envelope: Envelope[List[RiskAssessment]]
"""

import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class C3IngestClient:
    def __init__(self, platform_url: Optional[str] = None, component_key: Optional[str] = None):
        self.platform_url = (platform_url or os.getenv("PLATFORM_URL", "http://localhost:8000")).rstrip("/")
        self.component_key = component_key or os.getenv("C3_COMPONENT_KEY", "")
        self.endpoint = f"{self.platform_url}/api/v1/ingest/risk"

    def build_envelope(self, risk_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Wraps risk assessment records in Feature 24 standard Envelope.
        Validates contract constraints (schema_version='1.0', source='c3').
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        return {
            "schema_version": "1.0",
            "generated_at": now_utc,
            "source": "c3",
            "request_id": str(uuid.uuid4()),
            "data": risk_records,
        }

    def send_assessments(self, risk_records: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """
        Transmits risk assessments to LMS via HTTP POST with X-Component-Key header.
        Supports dry_run parameter for non-destructive contract validation.
        """
        if not self.component_key:
            raise ValueError(
                "C3_COMPONENT_KEY is required. Please set it in .env or pass it to C3IngestClient."
            )

        envelope = self.build_envelope(risk_records)
        headers = {
            "Content-Type": "application/json",
            "X-Component-Key": self.component_key,
        }
        params = {"dry_run": "true"} if dry_run else {}

        response = requests.post(self.endpoint, json=envelope, headers=headers, params=params, timeout=120)
        response.raise_for_status()
        return response.json()
