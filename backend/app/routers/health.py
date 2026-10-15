"""
backend/app/routers/health.py

Health-check endpoint: GET /api/v1/health
Returns HTTP 200 when the API is running and MongoDB Atlas is reachable,
or HTTP 503 when the database is unavailable.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get(
    "/health",
    summary="Service health check",
    description="Returns the operational status of the API and verifies MongoDB Atlas connectivity.",
    response_description="Health status object",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """
    Performs a live MongoDB Atlas connectivity check via ping command.
    """
    try:
        await db.command("ping")
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
