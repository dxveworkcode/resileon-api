from datetime import datetime

from pydantic import BaseModel, Field


class CommodityResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int = Field(..., description="Unique commodity record ID.")
    name: str = Field(..., description="Commodity name.", examples=["Wheat"])
    category: str = Field(
        ...,
        description="Commodity category. One of: food, energy, medical.",
        examples=["food"],
    )
    unit: str = Field(
        ..., description="Unit of measurement.", examples=["metric_ton"]
    )
    currency: str = Field(
        ..., description="ISO 4217 price currency code.", examples=["USD"]
    )
    current_price: float = Field(
        ..., description="Current market price in the specified currency.", examples=[312.50]
    )
    price_24h_ago: float | None = Field(
        None, description="Market price 24 hours ago.", examples=[305.00]
    )
    price_change_24h: float | None = Field(
        None,
        description="Percentage price change over the last 24 hours. Positive = increase.",
        examples=[2.46],
    )
    price_change_7d: float | None = Field(
        None,
        description="Percentage price change over the last 7 days.",
        examples=[-1.12],
    )
    source: str | None = Field(
        None,
        description="Data source identifier.",
        examples=["CBOT Futures (Yahoo Finance)"],
    )
    published_at: datetime = Field(
        ...,
        description=(
            "Timestamp when this record was published via the API (UTC). "
            "Always at least 1 hour after actual market data collection."
        ),
    )


class CommodityZoneResponse(BaseModel):
    zone_id: str = Field(..., description="Zone identifier.", examples=["sy-aleppo"])
    zone_name: str = Field(..., description="Zone display name.", examples=["Aleppo Region"])
    commodities: list[CommodityResponse] = Field(
        ..., description="List of commodity price records for this zone."
    )
    total: int = Field(..., description="Total number of commodity records returned.")
    timestamp: datetime = Field(..., description="Response generation timestamp (UTC).")
