"""
backend/app/routers/health.py

Health-check endpoint: GET /api/v1/health

Returns HTTP 200 when the API is running and the database is reachable,
or HTTP 503 when the database is unavailable.  Kubernetes/Docker liveness
and readiness probes should target this endpoint.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get(
    "/health",
    summary="Service health check",
    description=(
        "Returns the operational status of the API and verifies database "
        "connectivity by executing a lightweight `SELECT 1` query."
    ),
    response_description="Health status object",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Performs a live database connectivity check.

    - **status**: `"ok"` if everything is healthy, `"degraded"` otherwise.
    - **database**: `"connected"` or an error message string.
    """
    db_status: str
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": f"unreachable – {exc}",
            },
        ) from exc

    return {
        "status": "ok",
        "database": db_status,
    }
