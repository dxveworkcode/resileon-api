from datetime import datetime

from pydantic import BaseModel, Field


class LogisticsUpdateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int = Field(..., description="Unique logistics update ID.")
    zone_id: str = Field(..., description="Zone identifier.", examples=["ua-kherson"])
    hub_name: str = Field(
        ...,
        description="Name of the transport hub or route.",
        examples=["Port of Odessa"],
    )
    hub_type: str = Field(
        ...,
        description="Hub category. One of: port, border, airport, road.",
        examples=["port"],
    )
    status: str = Field(
        ...,
        description="Current operational status. One of: open, restricted, closed, unknown.",
        examples=["restricted"],
    )
    severity: str = Field(
        ...,
        description="Disruption severity. One of: none, low, moderate, high, critical.",
        examples=["high"],
    )
    description: str | None = Field(
        None, description="Human-readable status description sourced from news analysis."
    )
    source: str | None = Field(
        None, description="News feed or data source that triggered this update."
    )
    published_at: datetime = Field(
        ...,
        description=(
            "Timestamp when this record was published via the API (UTC). "
            "Always at least 1 hour after the triggering news item was collected."
        ),
    )


class LogisticsListResponse(BaseModel):
    updates: list[LogisticsUpdateResponse] = Field(
        ..., description="List of logistics status updates."
    )
    total: int = Field(..., description="Total number of updates returned.")
    timestamp: datetime = Field(..., description="Response generation timestamp (UTC).")
