"""
Redis-backed cache helpers.

All functions degrade silently when Redis is unavailable — the API
continues to serve data directly from the database with no disruption.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client: aioredis.Redis | None = None
_redis_warned: bool = False  # only log the connection warning once


async def get_redis() -> aioredis.Redis | None:
    global _redis_client, _redis_warned
    if _redis_client is None:
        try:
            client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await client.ping()
            _redis_client = client
            _redis_warned = False
            logger.info("Redis connection established.")
        except Exception as exc:
            if not _redis_warned:
                logger.warning(f"Redis unavailable ({exc}). Caching disabled.")
                _redis_warned = True
            _redis_client = None
    return _redis_client


class _ISODateTimeEncoder(json.JSONEncoder):
    """Serialize datetime objects as ISO 8601 strings."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def cache_get(key: str) -> Any | None:
    """Return cached value for *key*, or None on miss / Redis error."""
    client = await get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.debug(f"cache_get error for key={key!r}: {exc}")
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """Store *value* under *key* with an optional TTL (seconds)."""
    client = await get_redis()
    if client is None:
        return
    try:
        await client.setex(
            key,
            ttl or settings.cache_ttl,
            json.dumps(value, cls=_ISODateTimeEncoder),
        )
    except Exception as exc:
        logger.debug(f"cache_set error for key={key!r}: {exc}")


async def cache_delete(key: str) -> None:
    """Invalidate a cache entry."""
    client = await get_redis()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception as exc:
        logger.debug(f"cache_delete error for key={key!r}: {exc}")


def build_cache_key(*parts: str) -> str:
    """Build a deterministic cache key from string parts."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
