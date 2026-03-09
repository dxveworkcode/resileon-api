from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.zone import Zone
from app.schemas.status import StatusResponse
from app.services.rate_limiter import limiter

settings = get_settings()
router = APIRouter(prefix="/v1", tags=["Status"])

# Populated by the background worker after each successful scrape.
# In a multi-process deployment, move this into Redis.
_last_scrape_time: datetime | None = None


def set_last_scrape_time(dt: datetime) -> None:
    """Called by the data worker after each successful scrape cycle."""
    global _last_scrape_time
    _last_scrape_time = dt


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Server Health & Data Freshness",
    description=(
        "Returns current health status of the Resileon API server, including the timestamp "
        "of the last successful data scrape. Use this endpoint to verify service "
        "availability before making data requests."
    ),
    responses={
        200: {
            "description": "Server is operational.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "last_scrape": "2026-03-09T12:00:00Z",
                        "next_scrape": None,
                        "zones_tracked": 8,
                        "data_delay_note": (
                            "All data is delayed by a minimum of 1 hour "
                            "in accordance with our safety policy."
                        ),
                        "timestamp": "2026-03-09T13:05:00Z",
                    }
                }
            },
        }
    },
)
@limiter.limit("60/minute")
async def get_status(
    request: Request,  # required by SlowAPI
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    count_result = await db.execute(
        select(func.count()).select_from(Zone).where(Zone.is_active.is_(True))
    )
    zone_count = count_result.scalar_one_or_none() or 0

    return StatusResponse(
        status="healthy",
        version=settings.app_version,
        last_scrape=_last_scrape_time,
        next_scrape=None,
        zones_tracked=zone_count,
        data_delay_note=(
            "All data is delayed by a minimum of 1 hour in accordance with our safety policy. "
            "This ensures no information can be used for tactical advantage."
        ),
        timestamp=datetime.now(timezone.utc),
    )
