from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.commodity import Commodity
    from app.models.logistics import LogisticsUpdate


class Zone(Base):
    """A geographic region affected by conflict that Resileon tracks."""

    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "active", "post-conflict", "monitored"
    conflict_level: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    commodities: Mapped[list["Commodity"]] = relationship(
        "Commodity", back_populates="zone", cascade="all, delete-orphan"
    )
    logistics: Mapped[list["LogisticsUpdate"]] = relationship(
        "LogisticsUpdate", back_populates="zone", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Zone id={self.id!r} name={self.name!r}>"
