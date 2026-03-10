from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.metrics import MetricsOut
from backend.services import metrics as metrics_service

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics", response_model=MetricsOut)
async def get_metrics(db: AsyncSession = Depends(get_db)) -> MetricsOut:
    return await metrics_service.get_metrics(db)
