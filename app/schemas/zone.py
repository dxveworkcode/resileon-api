from datetime import datetime

from pydantic import BaseModel, Field


class ZoneResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique zone identifier.", examples=["sy-aleppo"])
    name: str = Field(..., description="Human-readable zone name.", examples=["Aleppo Region"])
    country: str = Field(..., description="Country the zone belongs to.", examples=["Syria"])
    region: str = Field(
        ..., description="Broader geographic region.", examples=["Middle East"]
    )
    conflict_level: str = Field(
        ...,
        description="Current conflict intensity. One of: active, post-conflict, monitored.",
        examples=["active"],
    )
    latitude: float | None = Field(None, description="Zone centre latitude (WGS-84).")
    longitude: float | None = Field(None, description="Zone centre longitude (WGS-84).")
    is_active: bool = Field(
        ..., description="Whether this zone is currently being tracked."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp of the last metadata update (UTC)."
    )


class ZoneListResponse(BaseModel):
    zones: list[ZoneResponse] = Field(..., description="List of active conflict zones.")
    total: int = Field(..., description="Total number of zones returned.")
    timestamp: datetime = Field(..., description="Response generation timestamp (UTC).")
