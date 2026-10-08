from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.services.aggregation import compute_weekly_features

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/aggregate-weekly", status_code=status.HTTP_200_OK)
async def trigger_weekly_aggregation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
) -> Dict[str, Any]:
    """
    Manually trigger the weekly aggregation job (Admin only).
    """
    count = await compute_weekly_features(db)
    await db.commit()
    return {"status": "ok", "records_upserted": count}
