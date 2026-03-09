# Run with: python -m worker.scheduler
# Scrapes commodities and logistics every 30 minutes; enforces the ≥1 h publication delay.

import asyncio
import logging
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base, init_db
from worker.news_parser import update_logistics
from worker.scraper import update_commodities
from worker.seed_data import seed_zones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# yfinance logs its own download errors at ERROR level even when we handle them
# gracefully in the scraper. Silence it completely — our WARNING is sufficient.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

settings = get_settings()

_engine = create_async_engine(settings.database_url, echo=False)
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _scrape_cycle() -> None:
    """Run one full data collection cycle (commodities + logistics)."""
    logger.info("─── Scrape cycle started ────────────────────────────────────")
    async with _SessionLocal() as db:
        commodity_count  = await update_commodities(db)
        logistics_count  = await update_logistics(db)

    logger.info(
        f"─── Scrape cycle complete — "
        f"{commodity_count} commodity records, {logistics_count} logistics updates ───"
    )

    # Optionally update the in-process status tracker used by /v1/status.
    # (In multi-process setups, persist this to Redis instead.)
    try:
        from app.routers.status import set_last_scrape_time
        set_last_scrape_time(datetime.now(timezone.utc))
    except Exception:
        pass


async def main() -> None:
    logger.info("Resileon Data Worker initialising...")

    await init_db()
    async with _SessionLocal() as db:
        await seed_zones(db)

    # Immediate first run so the API has data before the first scheduled slot
    await _scrape_cycle()

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _scrape_cycle,
        trigger=IntervalTrigger(minutes=30),
        id="resileon_scrape",
        name="Resileon full data scrape",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info("Scheduler running — scraping every 30 minutes. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker shutdown requested.")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
