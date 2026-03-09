from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone import Zone


class Commodity(Base):
    """Price record for an essential good in a specific conflict zone."""

    __tablename__ = "commodities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "food", "energy", "medical"
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    price_24h_ago: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_7d_ago: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # When the raw data was actually collected from the market source
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When this record was cleared for public API access (≥1 h after data_timestamp)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    zone: Mapped["Zone"] = relationship("Zone", back_populates="commodities")

    @property
    def price_change_24h(self) -> float | None:
        if self.price_24h_ago and self.price_24h_ago > 0:
            return round(
                ((self.current_price - self.price_24h_ago) / self.price_24h_ago) * 100, 2
            )
        return None

    @property
    def price_change_7d(self) -> float | None:
        if self.price_7d_ago and self.price_7d_ago > 0:
            return round(
                ((self.current_price - self.price_7d_ago) / self.price_7d_ago) * 100, 2
            )
        return None

    def __repr__(self) -> str:
        return f"<Commodity zone={self.zone_id!r} name={self.name!r} price={self.current_price}>"
