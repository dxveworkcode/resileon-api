<p align="center">
  <img src="docs/banner.png" alt="Resileon API" width="100%">
</p>

<p align="center">
  <a href="#endpoints">Endpoints</a> &nbsp;·&nbsp;
  <a href="#running-locally">Quick Start</a> &nbsp;·&nbsp;
  <a href="#deployment">Deploy</a> &nbsp;·&nbsp;
  <a href="#pricing">Pricing</a> &nbsp;·&nbsp;
  <a href="#data-safety">Safety Policy</a>
</p>

---

Resileon surfaces economic ground-truth from conflict-affected regions. It pulls commodity prices from global futures markets, scans public news feeds for supply-chain disruptions, and serves that data through a clean JSON API.

Every record carries a **mandatory one-hour publication delay**. This is a deliberate design constraint, not a limitation. Resileon cannot be used as a real-time tactical intelligence tool regardless of how it is configured.

**Commodities tracked:** Wheat · Crude Oil · Natural Gas · Corn · Diesel  
**Logistics signals:** Port closures · Border blockages · Road disruptions · Airspace status  
**Regions:** Eastern Europe · Middle East · Sub-Saharan Africa

---

## Endpoints

| Method | Path | What it returns |
|--------|------|-----------------|
| `GET` | [`/v1/status`](#get-v1status) | Server health and last scrape timestamp |
| `GET` | [`/v1/markets`](#get-v1markets) | All active conflict zones being monitored |
| `GET` | [`/v1/commodities/{zone_id}`](#get-v1commoditieszone_id) | Commodity prices with 24 h and 7 d change for one zone |
| `GET` | [`/v1/logistics`](#get-v1logistics) | Port, border, airport, and road status updates |

**Base URL:** `https://api.resileon.io/v1`  
**Interactive docs:** `/docs` (Swagger) · `/redoc`

---

## Running locally

**Requirements:** Python 3.12+

```bash
# 1. Copy config
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the data worker — seeds the database, then scrapes every 30 min
python -m worker.scheduler

# 4. Start the API server (new terminal)
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) to explore all endpoints interactively.

---

## GET /v1/status

Server health check. Returns the timestamp of the last successful scrape and the count of active zones.

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "last_scrape": "2026-03-09T12:00:00Z",
  "zones_tracked": 8,
  "data_delay_note": "All data is delayed by a minimum of 1 hour in accordance with our safety policy.",
  "timestamp": "2026-03-09T13:05:00Z"
}
```

---

## GET /v1/markets

Lists every conflict zone currently being monitored. The `id` field is what you pass to `/v1/commodities/{zone_id}`.

```json
{
  "zones": [
    {
      "id": "ua-kherson",
      "name": "Kherson Oblast",
      "country": "Ukraine",
      "region": "Eastern Europe",
      "conflict_level": "active",
      "latitude": 46.6354,
      "longitude": 32.6168,
      "is_active": true,
      "updated_at": "2026-03-09T12:00:00Z"
    }
  ],
  "total": 8,
  "timestamp": "2026-03-09T13:05:00Z"
}
```

---

## GET /v1/commodities/{zone_id}

Prices for essential goods in a specific zone, including 24 h and 7 d percentage change.

**Parameters**

| Name | In | Required | Description |
|------|----|----------|-------------|
| `zone_id` | path | yes | Zone ID from `/v1/markets` |
| `category` | query | no | Filter by `food`, `energy`, or `medical` |

```bash
GET /v1/commodities/sy-aleppo?category=food
```

```json
{
  "zone_id": "sy-aleppo",
  "zone_name": "Aleppo Region",
  "commodities": [
    {
      "id": 1,
      "name": "Wheat",
      "category": "food",
      "unit": "metric_ton",
      "currency": "USD",
      "current_price": 312.50,
      "price_24h_ago": 305.00,
      "price_change_24h": 2.46,
      "price_change_7d": -1.12,
      "source": "CBOT Wheat Futures (Yahoo Finance)",
      "published_at": "2026-03-09T12:00:00Z"
    }
  ],
  "total": 3,
  "timestamp": "2026-03-09T13:05:00Z"
}
```

**Errors**

| Code | Error | Cause |
|------|-------|-------|
| `404` | `zone_not_found` | `zone_id` doesn't match any active zone — check `/v1/markets` |
| `429` | `rate_limit_exceeded` | Daily request limit reached |

---

## GET /v1/logistics

Operational status for ports, border crossings, airports, and supply routes. Derived from automated analysis of public news feeds.

**Parameters**

| Name | In | Required | Description |
|------|----|----------|-------------|
| `zone_id` | query | no | Filter by zone |
| `status` | query | no | `open` · `restricted` · `closed` · `unknown` |
| `hub_type` | query | no | `port` · `border` · `airport` · `road` |

```json
{
  "updates": [
    {
      "id": 1,
      "zone_id": "ua-kherson",
      "hub_name": "Port of Odessa",
      "hub_type": "port",
      "status": "restricted",
      "severity": "high",
      "description": "Partial closure. Grain shipments operating at 40% capacity.",
      "source": "Reuters Feed",
      "published_at": "2026-03-09T12:00:00Z"
    }
  ],
  "total": 12,
  "timestamp": "2026-03-09T13:05:00Z"
}
```

---

## Error reference

All error responses follow the same shape — an `error` key, a human-readable `message`, and where relevant a pointer to fix the issue.

```json
{
  "error": "rate_limit_exceeded",
  "message": "You have exceeded the allowed request rate for this endpoint.",
  "detail": "Limit: 50/day",
  "upgrade_url": "https://rapidapi.com/resileon/api/resileon-api"
}
```

| Code | Meaning |
|------|---------|
| `404` | Zone not found, or the endpoint doesn't exist |
| `429` | Rate limit hit — check the `Retry-After` response header |
| `500` | Server fault — contact api@resileon.io |

---

## Data safety

Every record has two timestamps:

- **`data_timestamp`** — when the price or news signal was collected from its source
- **`published_at`** — when it became visible through the API (always at least 1 hour later)

The delay floor is controlled by `DATA_DELAY_HOURS` in your environment file. The application validates this at startup and **refuses to run** if the value is below `1`. There is no configuration path that allows real-time data to leak through.

---

## Deployment

### Docker

```bash
# Starts API + background worker + PostgreSQL + Redis
docker compose up -d

# Stream logs
docker compose logs -f api worker
```

### Render / Railway / Fly.io

1. Push to GitHub.
2. Create a **Web Service** connected to your repo.
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Create a second **Background Worker** service from the same repo.
   - Start command: `python -m worker.scheduler`
4. Add a managed PostgreSQL database and Redis instance from your provider.
5. Set environment variables from `.env.example` with your production credentials.

> Render's free tier spins down after inactivity. Upgrade to the $7/month Starter plan for an always-on server once you have paying users.

---

## Pricing

Available on [RapidAPI](https://rapidapi.com/resileon/api/resileon-api).

| Tier | Requests / day | Price |
|------|----------------|-------|
| Free | 50 | Free |
| Pro | 10,000 | $15-$30/month |
| Enterprise | Unlimited | Contact us |

The free tier is intentionally functional enough to build a working proof-of-concept. Researchers and analysts who build on it tend to upgrade.

---

## Conflict zones

| Zone ID | Name | Country | Region |
|---------|------|---------|--------|
| `ua-kherson` | Kherson Oblast | Ukraine | Eastern Europe |
| `ua-zaporizhzhia` | Zaporizhzhia Oblast | Ukraine | Eastern Europe |
| `sy-aleppo` | Aleppo Region | Syria | Middle East |
| `sy-idlib` | Idlib Governorate | Syria | Middle East |
| `ye-aden` | Aden Governorate | Yemen | Middle East |
| `sd-darfur` | Darfur Region | Sudan | Sub-Saharan Africa |
| `so-mogadishu` | Mogadishu Region | Somalia | Sub-Saharan Africa |
| `et-tigray` | Tigray Region | Ethiopia | Sub-Saharan Africa |

---

## Tests

```bash
pytest
```

Tests run against an in-memory SQLite database. No external services required.

---

© Resileon. All rights reserved.
