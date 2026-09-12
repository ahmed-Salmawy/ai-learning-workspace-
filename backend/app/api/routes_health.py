from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.correlation import get_correlation_id
from app.core.metrics import METRICS

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "correlationId": get_correlation_id() or "",
    }


@router.get("/metrics")
def metrics() -> dict[str, object]:
    return METRICS.snapshot()
