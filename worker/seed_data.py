"""
Resileon Seed Data — Conflict Zone Master List

Provides the initial set of conflict zones tracked by Resileon.
This is curated static reference data, not scraped content.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone import Zone

logger = logging.getLogger(__name__)

# fmt: off
ZONES: list[dict] = [
    {
        "id": "ua-kherson",
        "name": "Kherson Oblast",
        "country": "Ukraine",
        "region": "Eastern Europe",
        "conflict_level": "active",
        "latitude": 46.6354,
        "longitude": 32.6168,
    },
    {
        "id": "ua-zaporizhzhia",
        "name": "Zaporizhzhia Oblast",
        "country": "Ukraine",
        "region": "Eastern Europe",
        "conflict_level": "active",
        "latitude": 47.8388,
        "longitude": 35.1396,
    },
    {
        "id": "sy-aleppo",
        "name": "Aleppo Region",
        "country": "Syria",
        "region": "Middle East",
        "conflict_level": "post-conflict",
        "latitude": 36.2021,
        "longitude": 37.1343,
    },
    {
        "id": "sy-idlib",
        "name": "Idlib Governorate",
        "country": "Syria",
        "region": "Middle East",
        "conflict_level": "active",
        "latitude": 35.9304,
        "longitude": 36.6339,
    },
    {
        "id": "sd-darfur",
        "name": "Darfur Region",
        "country": "Sudan",
        "region": "Sub-Saharan Africa",
        "conflict_level": "active",
        "latitude": 13.5000,
        "longitude": 24.0000,
    },
    {
        "id": "ye-aden",
        "name": "Aden Governorate",
        "country": "Yemen",
        "region": "Middle East",
        "conflict_level": "active",
        "latitude": 12.7797,
        "longitude": 45.0367,
    },
    {
        "id": "so-mogadishu",
        "name": "Mogadishu Region",
        "country": "Somalia",
        "region": "Sub-Saharan Africa",
        "conflict_level": "active",
        "latitude": 2.0469,
        "longitude": 45.3418,
    },
    {
        "id": "et-tigray",
        "name": "Tigray Region",
        "country": "Ethiopia",
        "region": "Sub-Saharan Africa",
        "conflict_level": "post-conflict",
        "latitude": 14.0323,
        "longitude": 38.3168,
    },
]
# fmt: on


async def seed_zones(db: AsyncSession) -> int:
    """Insert zones that do not already exist. Returns the number of new rows inserted."""
    inserted = 0
    for zone_data in ZONES:
        result = await db.execute(select(Zone).where(Zone.id == zone_data["id"]))
        if result.scalar_one_or_none() is None:
            db.add(Zone(**zone_data))
            inserted += 1

    if inserted:
        await db.commit()
        logger.info(f"Seeded {inserted} new zone(s). Total defined: {len(ZONES)}.")
    else:
        logger.info("Zone seed: all zones already present, nothing to insert.")

    return inserted
