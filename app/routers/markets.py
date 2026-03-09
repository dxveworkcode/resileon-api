from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneListResponse, ZoneResponse
from app.services.cache import cache_get, cache_set
from app.services.rate_limiter import limiter

router = APIRouter(prefix="/v1", tags=["Markets"])


@router.get(
    "/markets",
    response_model=ZoneListResponse,
    summary="List Active Conflict Zone Markets",
    description=(
        "Returns all conflict zones currently monitored by Resileon. "
        "Each zone includes geographic metadata and conflict intensity level. "
        "Use the `id` field from this response to query commodity data via "
        "`/v1/commodities/{zone_id}`."
    ),
    responses={
        200: {
            "description": "List of active conflict zone markets.",
            "content": {
                "application/json": {
                    "example": {
                        "zones": [
                            {
                                "id": "sy-aleppo",
                                "name": "Aleppo Region",
                                "country": "Syria",
                                "region": "Middle East",
                                "conflict_level": "active",
                                "latitude": 36.2021,
                                "longitude": 37.1343,
                                "is_active": True,
                                "updated_at": "2026-03-09T12:00:00Z",
                            }
                        ],
                        "total": 8,
                        "timestamp": "2026-03-09T13:05:00Z",
                    }
                }
            },
        }
    },
)
@limiter.limit("100/minute")
async def list_markets(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ZoneListResponse:
    cache_key = "markets:all"
    cached = await cache_get(cache_key)
    if cached:
        # Refresh the timestamp so callers see the actual response time
        cached["timestamp"] = datetime.now(timezone.utc).isoformat()
        return cached

    result = await db.execute(
        select(Zone).where(Zone.is_active.is_(True)).order_by(Zone.region, Zone.name)
    )
    zones = result.scalars().all()

    response = ZoneListResponse(
        zones=[ZoneResponse.model_validate(z) for z in zones],
        total=len(zones),
        timestamp=datetime.now(timezone.utc),
    )

    await cache_set(cache_key, response.model_dump(), ttl=3600)
    return response
