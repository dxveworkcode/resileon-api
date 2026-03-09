from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "Resileon API"
    app_version: str = "1.0.0"
    app_description: str = (
        "Real-time economic impact metrics for conflict-affected regions."
    )
    debug: bool = False

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./resileon.db"
    database_url_sync: str = "sqlite:///./resileon.db"

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 3600  # seconds

    # ── Rate Limiting ──────────────────────────────────────────────────────────
    rate_limit_free: str = "50/day"
    rate_limit_pro: str = "10000/day"
    rate_limit_default: str = "200/minute"
    # ── RapidAPI ───────────────────────────────────────────────────────────────
    # Set this to the proxy secret from RapidAPI dashboard → Security.
    # Leave blank during local dev — check is skipped when empty.
    rapidapi_proxy_secret: str = ""
    # ── CORS ───────────────────────────────────────────────────────────────────
    # Plain string: "*" for all origins, or comma-separated list of URLs.
    allowed_origins: str = "*"

    # ── Data Safety ────────────────────────────────────────────────────────────
    # Minimum hours to hold collected data before it is served via the API.
    # Must remain ≥ 1 to prevent tactical information leakage.
    data_delay_hours: int = 1

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        # Render (and most PaaS) provide postgres:// or postgresql://.
        # SQLAlchemy's async engine requires the +asyncpg driver suffix.
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = "postgresql+asyncpg://" + v[len("postgres://"):]
            elif v.startswith("postgresql://"):
                v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @field_validator("data_delay_hours")
    @classmethod
    def enforce_minimum_delay(cls, v: int) -> int:
        if v < 1:
            raise ValueError("data_delay_hours must be at least 1 for safety compliance.")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
