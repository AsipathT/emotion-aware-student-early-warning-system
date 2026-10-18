"""
LMS API client for exporting weekly behavior records and ingesting trajectories.
"""

from typing import Any, Dict, List, Optional
import httpx

from service.schemas import BehaviorRecord


class LmsClient:
    """HTTP client communicating with LMS backend endpoints."""

    def __init__(
        self,
        base_url: str,
        component_key: str,
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.component_key = component_key
        self.client = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            timeout=timeout,
        )

    def close(self) -> None:
        """Closes the underlying httpx client."""
        self.client.close()

    def __enter__(self) -> "LmsClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def fetch_behavior(
        self,
        course_id: Optional[str] = None,
        week_from: Optional[int] = None,
        week_to: Optional[int] = None,
        pid: Optional[str] = None,
    ) -> List[BehaviorRecord]:
        """
        Paginates GET /api/v1/export/behavior until all records are collected or an empty page is returned.
        Page size is fixed at 500.
        """
        params: Dict[str, Any] = {"page_size": 500}
        if course_id is not None:
            params["course_id"] = course_id
        if week_from is not None:
            params["week_from"] = week_from
        if week_to is not None:
            params["week_to"] = week_to
        if pid is not None:
            params["pid"] = pid

        records: List[BehaviorRecord] = []
        page = 1
        headers = {"X-Component-Key": self.component_key}

        while True:
            params["page"] = page
            resp = self.client.get(
                "/api/v1/export/behavior",
                params=params,
                headers=headers,
            )
            if resp.status_code != 200:
                err_text = (
                    resp.text.replace(self.component_key, "***")
                    if self.component_key
                    else resp.text
                )
                raise RuntimeError(
                    f"LMS export failed (HTTP {resp.status_code}): {err_text[:200]}"
                )

            body = resp.json()
            raw_items = body.get("data", [])
            if not raw_items:
                break

            for item in raw_items:
                records.append(BehaviorRecord.model_validate(item))

            total = body.get("total", len(records))
            if len(records) >= total or len(raw_items) < params["page_size"]:
                break

            page += 1

        return records

    def post_trajectory(self, envelope: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        """
        Posts trajectory records to POST /api/v1/ingest/trajectory.
        Splits into chunks of 1000 records if needed and merges count tallies.
        """
        all_records = envelope.get("data", [])
        chunk_size = 1000
        if not all_records:
            chunks = [[]]
        else:
            chunks = [
                all_records[i : i + chunk_size]
                for i in range(0, len(all_records), chunk_size)
            ]

        headers = {"X-Component-Key": self.component_key}
        merged: Dict[str, Any] = {
            "run_id": "",
            "schema_version": envelope.get("schema_version", "1.0"),
            "dry_run": dry_run,
            "received": 0,
            "accepted": 0,
            "rejected": 0,
            "created": 0,
            "updated": 0,
            "rejected_records": [],
        }

        for chunk in chunks:
            sub_envelope = dict(envelope)
            sub_envelope["data"] = chunk

            resp = self.client.post(
                "/api/v1/ingest/trajectory",
                params={"dry_run": "true" if dry_run else "false"},
                json=sub_envelope,
                headers=headers,
            )
            if resp.status_code != 200:
                err_text = (
                    resp.text.replace(self.component_key, "***")
                    if self.component_key
                    else resp.text
                )
                raise RuntimeError(
                    f"LMS ingest failed (HTTP {resp.status_code}): {err_text[:200]}"
                )

            res = resp.json()
            if res.get("run_id"):
                merged["run_id"] = res["run_id"]
            if res.get("schema_version"):
                merged["schema_version"] = res["schema_version"]
            merged["received"] += res.get("received", 0)
            merged["accepted"] += res.get("accepted", 0)
            merged["rejected"] += res.get("rejected", 0)
            merged["created"] += res.get("created", 0)
            merged["updated"] += res.get("updated", 0)
            if res.get("rejected_records"):
                merged["rejected_records"].extend(res["rejected_records"])

        return merged
