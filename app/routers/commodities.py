from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.commodity import Commodity
from app.models.zone import Zone
from app.schemas.commodity import CommodityResponse, CommodityZoneResponse
from app.services.cache import cache_get, cache_set
from app.services.rate_limiter import limiter

router = APIRouter(prefix="/v1", tags=["Commodities"])


@router.get(
    "/commodities/{zone_id}",
    response_model=CommodityZoneResponse,
    summary="Commodity Prices for a Conflict Zone",
    description=(
        "Returns essential goods with current prices and 24 h / 7 d change percentages "
        "for the specified conflict zone. "
        "All prices are delayed by at least 1 hour per Resileon's data safety policy. "
        "Obtain valid `zone_id` values from `/v1/markets`."
    ),
    responses={
        200: {
            "description": "Commodity price data for the requested zone.",
            "content": {
                "application/json": {
                    "example": {
                        "zone_id": "sy-aleppo",
                        "zone_name": "Aleppo Region",
                        "commodities": [
                            {
                                "id": 1,
                                "name": "Wheat",
                                "category": "food",
                                "unit": "metric_ton",
                                "currency": "USD",
                                "current_price": 312.50,
                                "price_24h_ago": 305.00,
                                "price_change_24h": 2.46,
                                "price_change_7d": -1.12,
                                "source": "CBOT Futures (Yahoo Finance)",
                                "published_at": "2026-03-09T12:00:00Z",
                            }
                        ],
                        "total": 6,
                        "timestamp": "2026-03-09T13:05:00Z",
                    }
                }
            },
        },
        404: {
            "description": "Zone not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": "zone_not_found",
                            "message": "No active zone with id 'xyz' was found.",
                            "available_zones_url": "/v1/markets",
                        }
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
async def get_commodities(
    request: Request,
    zone_id: str,
    category: str | None = Query(
        None,
        description="Filter results by category. Accepted values: `food`, `energy`, `medical`.",
    ),
    db: AsyncSession = Depends(get_db),
) -> CommodityZoneResponse:
    # Validate zone exists and is active
    zone_result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.is_active.is_(True))
    )
    zone = zone_result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "zone_not_found",
                "message": f"No active zone with id '{zone_id}' was found.",
                "available_zones_url": "/v1/markets",
            },
        )

    cache_key = f"commodities:{zone_id}:{category or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        cached["timestamp"] = datetime.now(timezone.utc).isoformat()
        return cached

    query = select(Commodity).where(Commodity.zone_id == zone_id)
    if category:
        query = query.where(Commodity.category == category)
    query = query.order_by(Commodity.category, Commodity.name)

    result = await db.execute(query)
    records = result.scalars().all()

    commodity_list = [
        CommodityResponse(
            id=c.id,
            name=c.name,
            category=c.category,
            unit=c.unit,
            currency=c.currency,
            current_price=c.current_price,
            price_24h_ago=c.price_24h_ago,
            price_change_24h=c.price_change_24h,
            price_change_7d=c.price_change_7d,
            source=c.source,
            published_at=c.published_at,
        )
        for c in records
    ]

    response = CommodityZoneResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        commodities=commodity_list,
        total=len(commodity_list),
        timestamp=datetime.now(timezone.utc),
    )

    await cache_set(cache_key, response.model_dump(), ttl=3600)
    return response
