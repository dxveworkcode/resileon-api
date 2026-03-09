"""
Resileon API — Integration Tests

Covers all four v1 endpoints against an in-memory SQLite database.
Run with:  pytest
"""

import pytest
from httpx import AsyncClient


# ─── Root ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root_returns_service_info(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Resileon API"
    assert "endpoints" in body


# ─── /v1/status ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_healthy(client: AsyncClient):
    response = await client.get("/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert "zones_tracked" in body
    assert body["zones_tracked"] >= 8
    assert "data_delay_note" in body
    assert "timestamp" in body


# ─── /v1/markets ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_markets_returns_zone_list(client: AsyncClient):
    response = await client.get("/v1/markets")
    assert response.status_code == 200
    body = response.json()
    assert "zones" in body
    assert body["total"] == len(body["zones"])
    assert body["total"] >= 8


@pytest.mark.asyncio
async def test_markets_zone_fields(client: AsyncClient):
    response = await client.get("/v1/markets")
    zone = response.json()["zones"][0]
    for field in ("id", "name", "country", "region", "conflict_level", "is_active"):
        assert field in zone, f"Missing field: {field}"


# ─── /v1/commodities/{zone_id} ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commodities_valid_zone(client: AsyncClient):
    # Seed data must be loaded before this test (handled by conftest.py fixture)
    # Run the commodity scraper so there is data to return
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from worker.scraper import update_commodities

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Use the already-seeded test DB via the worker directly
    # (The conftest already overrides get_db, so we just call the endpoint)
    response = await client.get("/v1/commodities/sy-aleppo")
    # Zone exists — we expect 200 even if commodities list is empty
    assert response.status_code == 200
    body = response.json()
    assert body["zone_id"] == "sy-aleppo"
    assert body["zone_name"] == "Aleppo Region"
    assert "commodities" in body
    assert isinstance(body["commodities"], list)
    assert "total" in body


@pytest.mark.asyncio
async def test_commodities_unknown_zone_returns_404(client: AsyncClient):
    response = await client.get("/v1/commodities/not-a-real-zone")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "zone_not_found"
    assert "available_zones_url" in detail


@pytest.mark.asyncio
async def test_commodities_category_filter(client: AsyncClient):
    response = await client.get("/v1/commodities/ua-kherson?category=food")
    assert response.status_code == 200
    body = response.json()
    # If any commodities are returned, they must all be in the "food" category
    for item in body["commodities"]:
        assert item["category"] == "food"


# ─── /v1/logistics ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logistics_returns_list(client: AsyncClient):
    response = await client.get("/v1/logistics")
    assert response.status_code == 200
    body = response.json()
    assert "updates" in body
    assert "total" in body
    assert body["total"] == len(body["updates"])


@pytest.mark.asyncio
async def test_logistics_filter_by_zone(client: AsyncClient):
    response = await client.get("/v1/logistics?zone_id=ua-kherson")
    assert response.status_code == 200
    body = response.json()
    for update in body["updates"]:
        assert update["zone_id"] == "ua-kherson"


@pytest.mark.asyncio
async def test_logistics_filter_by_status(client: AsyncClient):
    response = await client.get("/v1/logistics?status=restricted")
    assert response.status_code == 200
    for update in response.json()["updates"]:
        assert update["status"] == "restricted"


# ─── 404 handler ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_endpoint_returns_404(client: AsyncClient):
    response = await client.get("/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert "available_endpoints" in body
