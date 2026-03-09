from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone import Zone


class LogisticsUpdate(Base):
    """Operational status record for a transport hub or supply route."""

    __tablename__ = "logistics_updates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hub_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "port" | "border" | "airport" | "road"
    hub_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "open" | "restricted" | "closed" | "unknown"
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # "none" | "low" | "moderate" | "high" | "critical"
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # When the raw signal was collected (from news feed publication time)
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When this record was cleared for public API access (≥1 h after data_timestamp)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    zone: Mapped["Zone"] = relationship("Zone", back_populates="logistics")

    def __repr__(self) -> str:
        return f"<LogisticsUpdate zone={self.zone_id!r} hub={self.hub_name!r} status={self.status!r}>"
