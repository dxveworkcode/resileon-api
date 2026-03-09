"""
Resileon API — Application Entry Point

Run with:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import commodities, logistics, markets, status
from app.services.rate_limiter import limiter, rate_limit_exceeded_handler

_STATIC = Path("static")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Resileon API starting — initialising database...")
    await init_db()

    # Seed zones and run an immediate scrape, then schedule every 30 min.
    # Running inside the API process avoids the need for a separate worker service.
    from worker.seed_data import seed_zones
    from worker.scraper import update_commodities
    from worker.news_parser import update_logistics
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.database import engine

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _scrape_cycle():
        async with SessionLocal() as db:
            await seed_zones(db)
            commodity_count = await update_commodities(db)
            logistics_count = await update_logistics(db)
        logger.info(f"Scrape complete: {commodity_count} commodity records, {logistics_count} logistics updates.")
        try:
            from app.routers.status import set_last_scrape_time
            from datetime import datetime, timezone
            set_last_scrape_time(datetime.now(timezone.utc))
        except Exception:
            pass

    await _scrape_cycle()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scrape_cycle,
        trigger=IntervalTrigger(minutes=30),
        id="scrape",
        name="Resileon data scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — scraping every 30 minutes.")

    yield

    scheduler.shutdown(wait=False)
    logger.info("Resileon API shutting down.")


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**Resileon** is a specialized data engine providing real-time economic impact "
        "metrics for conflict-affected regions.\n\n"
        "## Data Coverage\n"
        "- **Commodity Prices:** Wheat, crude oil, natural gas, corn, diesel, and more\n"
        "- **Logistics Status:** Port closures, border blockages, supply route disruptions\n"
        "- **Multi-Zone Tracking:** Active conflict zones across Middle East, "
        "Eastern Europe, and Sub-Saharan Africa\n\n"
        "## Safety Policy\n"
        "All data is aggregated from public sources and **delayed by a minimum of 1 hour** "
        "before publication. Resileon cannot be used as a real-time tactical intelligence "
        "tool by design.\n\n"
        "## Rate Limits\n"
        "| Tier | Requests/day | Price |\n"
        "|------|-------------|-------|\n"
        "| Free | 50 | Free |\n"
        "| Pro  | 10,000 | $15-$30/month |\n\n"
        "Obtain API keys via [RapidAPI](https://rapidapi.com)."
    ),
    contact={"name": "Resileon API Support", "email": "api@resileon.io"},
    license_info={"name": "Proprietary"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,   # No cookies / sessions — API-key only
    allow_methods=["GET"],     # Read-only public API
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(status.router)
app.include_router(markets.router)
app.include_router(commodities.router)
app.include_router(logistics.router)

if _STATIC.is_dir():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Global Error Handlers ────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Router raised a structured 404 (e.g. zone_not_found) — pass it through as-is.
    if isinstance(getattr(exc, "detail", None), dict):
        return JSONResponse(status_code=404, content={"detail": exc.detail})
    # Generic 404 — no route matched.
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": "The requested endpoint does not exist.",
            "available_endpoints": [
                "GET /v1/status",
                "GET /v1/markets",
                "GET /v1/commodities/{zone_id}",
                "GET /v1/logistics",
            ],
            "docs_url": "/docs",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled internal error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
            "support": "api@resileon.io",
        },
    )


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    ico = _STATIC / "favicon.ico"
    if ico.is_file():
        return FileResponse(str(ico))
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "status": "/v1/status",
            "markets": "/v1/markets",
            "commodities": "/v1/commodities/{zone_id}",
            "logistics": "/v1/logistics",
        },
    }
