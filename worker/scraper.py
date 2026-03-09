# Commodity scraper — pulls futures prices from Yahoo Finance and upserts them per zone.

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.commodity import Commodity
from app.models.zone import Zone

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Commodity catalogue ──────────────────────────────────────────────────────

COMMODITY_CATALOGUE: dict[str, dict[str, str]] = {
    "wheat": {
        "name": "Wheat",
        "category": "food",
        "unit": "metric_ton",
        "currency": "USD",
        "ticker": "ZW=F",
        "source": "CBOT Wheat Futures (Yahoo Finance)",
    },
    "crude_oil": {
        "name": "Crude Oil (Brent)",
        "category": "energy",
        "unit": "barrel",
        "currency": "USD",
        "ticker": "BZ=F",
        "source": "ICE Brent Futures (Yahoo Finance)",
    },
    "natural_gas": {
        "name": "Natural Gas",
        "category": "energy",
        "unit": "MMBtu",
        "currency": "USD",
        "ticker": "NG=F",
        "source": "NYMEX Futures (Yahoo Finance)",
    },
    "corn": {
        "name": "Corn",
        "category": "food",
        "unit": "bushel",
        "currency": "USD",
        "ticker": "ZC=F",
        "source": "CBOT Corn Futures (Yahoo Finance)",
    },
    "sunflower_oil": {
        "name": "Sunflower Oil",
        "category": "food",
        "unit": "metric_ton",
        "currency": "USD",
        "ticker": None,   # no liquid futures; uses simulated data
        "source": "UN FAO Food Price Index (simulated)",
    },
    "diesel": {
        "name": "Diesel",
        "category": "energy",
        "unit": "liter",
        "currency": "USD",
        "ticker": "HO=F",   # Heating Oil as proxy
        "source": "NYMEX Heating Oil Futures (Yahoo Finance)",
    },
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _apply_data_delay(raw: dict[str, Any]) -> dict[str, Any]:
    # published_at must be at least DATA_DELAY_HOURS after the data was collected
    now = datetime.now(timezone.utc)
    data_ts: datetime = raw["data_timestamp"]
    if isinstance(data_ts, str):
        data_ts = datetime.fromisoformat(data_ts)

    earliest_publish = data_ts + timedelta(hours=settings.data_delay_hours)
    raw["published_at"] = max(earliest_publish, now)
    return raw


def _generate_fallback_prices() -> dict[str, dict[str, Any]]:
    import random

    now = datetime.now(timezone.utc)
    data_ts = now - timedelta(hours=2)

    base_prices: dict[str, float] = {
        "wheat": 310.0,
        "crude_oil": 82.50,
        "natural_gas": 2.85,
        "corn": 430.0,
        "sunflower_oil": 950.0,
        "diesel": 0.95,
    }

    return {
        key: {
            "current_price": round(base * (1 + random.uniform(-0.03, 0.03)), 4),
            "price_24h_ago": round(base * (1 + random.uniform(-0.02, 0.02)), 4),
            "price_7d_ago": round(base * (1 + random.uniform(-0.05, 0.05)), 4),
            "data_timestamp": data_ts,
            "source": COMMODITY_CATALOGUE[key]["source"] + " (simulated)",
        }
        for key, base in base_prices.items()
    }


async def fetch_commodity_prices() -> dict[str, dict[str, Any]]:
    import requests

    # Yahoo Finance chart API v8 — same data yfinance wraps but called directly.
    # yfinance's own HTTP layer fails with JSONDecodeError on some environments;
    # a plain requests call with a browser UA works reliably.
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    })

    now = datetime.now(timezone.utc)
    data_ts = now - timedelta(hours=2)
    prices: dict[str, dict[str, Any]] = {}

    for key, meta in COMMODITY_CATALOGUE.items():
        ticker = meta.get("ticker")
        if not ticker:
            continue
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            resp = session.get(url, params={"interval": "1h", "range": "8d"}, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            result = payload["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            # Strip None values that mark non-trading hours
            closes = [c for c in closes if c is not None]
            if not closes:
                continue
            prices[key] = {
                "current_price": round(closes[-1], 4),
                "price_24h_ago": round(closes[-24], 4) if len(closes) >= 24 else None,
                "price_7d_ago": round(closes[0], 4) if len(closes) >= 2 else None,
                "data_timestamp": data_ts,
                "source": meta["source"],
            }
            logger.info(f"Live price: {ticker} = {prices[key]['current_price']}")
        except Exception as exc:
            logger.warning(f"Price fetch failed for {ticker}, using fallback: {exc}")

    fallback = _generate_fallback_prices()
    for key in COMMODITY_CATALOGUE:
        if key not in prices:
            prices[key] = fallback[key]

    return prices


# ─── Database update ──────────────────────────────────────────────────────────

async def update_commodities(db: AsyncSession) -> int:
    """
    Fetch prices and upsert commodity rows for every active zone.
    Returns the total number of records written.
    """
    prices = await fetch_commodity_prices()
    if not prices:
        logger.warning("No price data received — skipping commodity update.")
        return 0

    zones_result = await db.execute(select(Zone).where(Zone.is_active.is_(True)))
    zones = zones_result.scalars().all()

    written = 0
    for zone in zones:
        for key, raw_price in prices.items():
            meta = COMMODITY_CATALOGUE[key]
            delayed = _apply_data_delay(dict(raw_price))

            existing_result = await db.execute(
                select(Commodity).where(
                    Commodity.zone_id == zone.id,
                    Commodity.name == meta["name"],
                )
            )
            record = existing_result.scalar_one_or_none()

            if record:
                record.current_price = delayed["current_price"]
                record.price_24h_ago = delayed.get("price_24h_ago")
                record.price_7d_ago = delayed.get("price_7d_ago")
                record.data_timestamp = delayed["data_timestamp"]
                record.published_at = delayed["published_at"]
                record.source = delayed.get("source")
            else:
                db.add(
                    Commodity(
                        zone_id=zone.id,
                        name=meta["name"],
                        category=meta["category"],
                        unit=meta["unit"],
                        currency=meta["currency"],
                        current_price=delayed["current_price"],
                        price_24h_ago=delayed.get("price_24h_ago"),
                        price_7d_ago=delayed.get("price_7d_ago"),
                        data_timestamp=delayed["data_timestamp"],
                        published_at=delayed["published_at"],
                        source=delayed.get("source"),
                    )
                )
            written += 1

    await db.commit()
    logger.info(f"Commodity update complete — {written} records across {len(zones)} zone(s).")
    return written
