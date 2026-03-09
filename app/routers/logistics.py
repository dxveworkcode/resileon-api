from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.logistics import LogisticsUpdate
from app.schemas.logistics import LogisticsListResponse, LogisticsUpdateResponse
from app.services.cache import cache_get, cache_set
from app.services.rate_limiter import limiter

router = APIRouter(prefix="/v1", tags=["Logistics"])


@router.get(
    "/logistics",
    response_model=LogisticsListResponse,
    summary="Supply Chain & Transport Hub Status",
    description=(
        "Returns operational status for ports, border crossings, airports, and supply routes "
        "in conflict-affected areas. Status flags are derived from automated analysis of public "
        "news feeds and are delayed by at least 1 hour per Resileon's safety policy."
    ),
    responses={
        200: {
            "description": "Logistics status updates.",
            "content": {
                "application/json": {
                    "example": {
                        "updates": [
                            {
                                "id": 1,
                                "zone_id": "ua-kherson",
                                "hub_name": "Port of Odessa",
                                "hub_type": "port",
                                "status": "restricted",
                                "severity": "high",
                                "description": (
                                    "Partial closure due to regional conflict activity. "
                                    "Grain shipments operating at 40% capacity."
                                ),
                                "source": "Reuters Feed",
                                "published_at": "2026-03-09T12:00:00Z",
                            }
                        ],
                        "total": 12,
                        "timestamp": "2026-03-09T13:05:00Z",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded.",
            "content": {
                "application/json": {
                    "example": {
                        "error": "rate_limit_exceeded",
                        "message": "You have exceeded the allowed request rate.",
                        "upgrade_url": "https://rapidapi.com/resileon/api/resileon-api",
                    }
                }
            },
        },
    },
)
@limiter.limit("60/minute")
async def get_logistics(
    request: Request,
    zone_id: str | None = Query(
        None,
        description="Filter by zone ID. Obtain valid IDs from `/v1/markets`.",
    ),
    status: str | None = Query(
        None,
        description="Filter by operational status. Accepted values: `open`, `restricted`, `closed`, `unknown`.",
    ),
    hub_type: str | None = Query(
        None,
        description="Filter by hub type. Accepted values: `port`, `border`, `airport`, `road`.",
    ),
    db: AsyncSession = Depends(get_db),
) -> LogisticsListResponse:
    cache_key = f"logistics:{zone_id or 'all'}:{status or 'all'}:{hub_type or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        cached["timestamp"] = datetime.now(timezone.utc).isoformat()
        return cached

    query = select(LogisticsUpdate).order_by(LogisticsUpdate.published_at.desc())
    if zone_id:
        query = query.where(LogisticsUpdate.zone_id == zone_id)
    if status:
        query = query.where(LogisticsUpdate.status == status)
    if hub_type:
        query = query.where(LogisticsUpdate.hub_type == hub_type)

    result = await db.execute(query)
    updates = result.scalars().all()

    response = LogisticsListResponse(
        updates=[LogisticsUpdateResponse.model_validate(u) for u in updates],
        total=len(updates),
        timestamp=datetime.now(timezone.utc),
    )

    await cache_set(cache_key, response.model_dump(), ttl=3600)
    return response
