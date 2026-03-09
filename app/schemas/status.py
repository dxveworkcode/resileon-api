from datetime import datetime

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    status: str = Field(
        ...,
        description="Server health status.",
        examples=["healthy"],
    )
    version: str = Field(
        ...,
        description="API version string.",
        examples=["1.0.0"],
    )
    last_scrape: datetime | None = Field(
        None,
        description="Timestamp of the last successful data scrape (UTC). Null if no scrape has completed since startup.",
    )
    next_scrape: datetime | None = Field(
        None,
        description="Estimated timestamp of the next scheduled scrape (UTC).",
    )
    zones_tracked: int = Field(
        ...,
        description="Number of active conflict zones currently being monitored.",
        examples=[8],
    )
    data_delay_note: str = Field(
        ...,
        description="Notice regarding the mandatory data delay policy.",
    )
    timestamp: datetime = Field(
        ...,
        description="Current server time (UTC).",
    )
