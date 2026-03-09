# News parser — scans RSS feeds for logistics disruption signals and upserts LogisticsUpdate records.

import email.utils
import html as _html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.logistics import LogisticsUpdate
from app.models.zone import Zone

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Feed configuration ───────────────────────────────────────────────────────

RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://reliefweb.int/updates/rss.xml",
    "https://www.un.org/press/en/rss.xml",
]

# Keywords mapped to (status, severity)
DISRUPTION_SIGNALS: dict[str, tuple[str, str]] = {
    "port closed":        ("closed",     "high"),
    "port closure":       ("closed",     "high"),
    "border blocked":     ("restricted", "high"),
    "border closed":      ("closed",     "high"),
    "border crossing closed": ("closed", "high"),
    "embargo":            ("restricted", "high"),
    "blockade":           ("restricted", "high"),
    "shipping suspended": ("closed",     "moderate"),
    "route suspended":    ("closed",     "moderate"),
    "supply route":       ("restricted", "moderate"),
    "road closed":        ("closed",     "moderate"),
    "under attack":       ("closed",     "critical"),
    "shelled":            ("closed",     "critical"),
    "airstrike":          ("closed",     "critical"),
    "reopened":           ("open",       "none"),
    "resumed operations": ("open",       "none"),
}

HUB_TYPE_SIGNALS: dict[str, tuple[str, ...]] = {
    "port":    ("port", "harbor", "harbour", "seaport", "maritime", "terminal"),
    "border":  ("border crossing", "border checkpoint", "border point", "land crossing"),
    "airport": ("airport", "airspace", "air corridor"),
    "road":    ("highway", "road", "corridor", "supply route", "convoy"),
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _detect_disruption(text: str) -> tuple[str, str] | None:
    """Return (status, severity) for the first matching signal, or None."""
    lower = text.lower()
    for phrase, result in DISRUPTION_SIGNALS.items():
        if phrase in lower:
            return result
    return None


def _detect_hub_type(text: str) -> str:
    lower = text.lower()
    for hub_type, keywords in HUB_TYPE_SIGNALS.items():
        if any(kw in lower for kw in keywords):
            return hub_type
    return "road"


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities from untrusted feed content."""
    text = re.sub(r'<[^>]+>', '', text)
    return _html.unescape(text).strip()


def _extract_hub_name(title: str) -> str | None:
    """Extract a named logistics hub from a headline. Returns None if no hub identified."""
    patterns = [
        r"(?:port of|port at)\s+([\w\s\-]+?)(?:\s+(?:closed|blocked|restricted|under|is|in)|$)",
        r"([\w\s\-]+?)\s+(?:port|harbor|harbour|terminal)(?:\s|$)",
        r"([\w\s\-]+?)\s+(?:border crossing|border checkpoint)(?:\s|$)",
        r"([\w\s\-]+?)\s+airport(?:\s|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()[:200]
    return None  # Title doesn't name a specific logistics hub


def _parse_feed_date(raw: str) -> datetime:
    try:
        return datetime(*email.utils.parsedate(raw)[:6], tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=2)


def _apply_data_delay(data_ts: datetime) -> datetime:
    """Return the earliest allowed published_at for the given data timestamp."""
    now = datetime.now(timezone.utc)
    earliest = data_ts + timedelta(hours=settings.data_delay_hours)
    return max(earliest, now)


# ─── Fallback / simulation ────────────────────────────────────────────────────

def _fallback_logistics() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    data_ts = now - timedelta(hours=2)
    pub_ts = _apply_data_delay(data_ts)

    return [
        {
            "hub_name": "Port of Odessa",
            "hub_type": "port",
            "status": "restricted",
            "severity": "high",
            "description": (
                "Partial closure due to regional conflict activity. "
                "Grain shipments operating at 40% capacity."
            ),
            "source": "Simulated Data",
            "data_timestamp": data_ts,
            "published_at": pub_ts,
        },
        {
            "hub_name": "Bab al-Hawa Border Crossing",
            "hub_type": "border",
            "status": "restricted",
            "severity": "moderate",
            "description": (
                "Cross-border aid deliveries subject to extended inspection. "
                "Delays of 4–8 hours reported."
            ),
            "source": "Simulated Data",
            "data_timestamp": data_ts,
            "published_at": pub_ts,
        },
        {
            "hub_name": "Aden Container Terminal",
            "hub_type": "port",
            "status": "open",
            "severity": "low",
            "description": "Port operational with reduced throughput. Security escort required.",
            "source": "Simulated Data",
            "data_timestamp": data_ts,
            "published_at": pub_ts,
        },
        {
            "hub_name": "N1 Highway — Kharkiv Corridor",
            "hub_type": "road",
            "status": "closed",
            "severity": "critical",
            "description": (
                "Main supply route closed due to active hostilities near Kupiansk. "
                "Alternative routing via N2 recommended."
            ),
            "source": "Simulated Data",
            "data_timestamp": data_ts,
            "published_at": pub_ts,
        },
        {
            "hub_name": "Khartoum International Airport",
            "hub_type": "airport",
            "status": "closed",
            "severity": "critical",
            "description": "Airspace closed. Humanitarian flights rerouted via Port Sudan.",
            "source": "Simulated Data",
            "data_timestamp": data_ts,
            "published_at": pub_ts,
        },
    ]


# ─── RSS fetch ────────────────────────────────────────────────────────────────

async def fetch_logistics_signals() -> list[dict[str, Any]]:
    """
    Parse RSS feeds for disruption signals.
    Returns a list of raw logistics event dicts.
    Falls back to simulated data if feedparser is unavailable or all feeds fail.
    """
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed — using simulated logistics data.")
        return _fallback_logistics()

    events: list[dict[str, Any]] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:50]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                body    = f"{title} {summary}"

                result = _detect_disruption(body)
                if result is None:
                    continue

                status, severity = result
                data_ts = _parse_feed_date(entry.get("published", ""))

                hub_name = _extract_hub_name(title)
                if hub_name is None:
                    continue  # General news — no specific logistics hub identified

                events.append(
                    {
                        "hub_name":       hub_name,
                        "hub_type":       _detect_hub_type(body),
                        "status":         status,
                        "severity":       severity,
                        "description":    _strip_html(summary or title)[:500],
                        "source":         feed.feed.get("title", url),
                        "data_timestamp": data_ts,
                        "published_at":   _apply_data_delay(data_ts),
                    }
                )
        except Exception as exc:
            logger.warning(f"Failed to parse feed {url}: {exc}")

    if not events:
        logger.info("No disruption signals found in feeds — using simulated fallback.")
        return _fallback_logistics()

    return events


# ─── Database update ──────────────────────────────────────────────────────────

async def update_logistics(db: AsyncSession) -> int:
    """
    Fetch news signals and upsert LogisticsUpdate records.
    Returns the number of new records inserted.
    """
    events = await fetch_logistics_signals()

    zones_result = await db.execute(select(Zone).where(Zone.is_active.is_(True)))
    zones = zones_result.scalars().all()
    if not zones:
        return 0

    inserted = 0
    for event in events:
        # Use explicit zone hint (curated/fallback data) or geographic text match
        zone_hint = event.get("zone_hint")
        if zone_hint:
            matched = next((z for z in zones if z.id == zone_hint), None)
        else:
            combined = f"{event['hub_name']} {event.get('description', '')}".lower()
            matched = next(
                (
                    z for z in zones
                    if z.name.lower() in combined
                    or z.country.lower() in combined
                ),
                None,
            )
        if matched is None:
            continue  # Skip events with no geographic match rather than misassigning

        existing_result = await db.execute(
            select(LogisticsUpdate).where(
                LogisticsUpdate.zone_id == matched.id,
                LogisticsUpdate.hub_name == event["hub_name"],
            )
        )
        record = existing_result.scalar_one_or_none()

        if record:
            record.status         = event["status"]
            record.severity       = event["severity"]
            record.description    = event.get("description")
            record.source         = event.get("source")
            record.data_timestamp = event["data_timestamp"]
            record.published_at   = event["published_at"]
        else:
            db.add(
                LogisticsUpdate(
                    zone_id=matched.id,
                    hub_name=event["hub_name"],
                    hub_type=event["hub_type"],
                    status=event["status"],
                    severity=event["severity"],
                    description=event.get("description"),
                    source=event.get("source"),
                    data_timestamp=event["data_timestamp"],
                    published_at=event["published_at"],
                )
            )
            inserted += 1

    await db.commit()
    logger.info(f"Logistics update complete — {inserted} new record(s) inserted.")
    return inserted
