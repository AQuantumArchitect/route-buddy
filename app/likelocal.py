"""Read-only client for likelocal's public API. Never calls /api/refresh or anything that writes."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

BASE_URL = os.environ.get("LIKELOCAL_URL", "https://likelocal-production.up.railway.app").rstrip("/")
_SLUG = re.compile(r"[^a-z0-9-]+")
MAX_PLACES = 12


def slugify(area: str) -> str:
    """'Austin, TX' -> 'austin-tx'; ZIP codes pass through unchanged."""
    return _SLUG.sub("-", area.strip().lower()).strip("-")


async def _get_events(area: str, client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    owned = client is None
    client = client or httpx.AsyncClient(timeout=15)
    try:
        resp = await client.get(f"{BASE_URL}/api/events", params={"city": slugify(area)})
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    finally:
        if owned:
            await client.aclose()


def _place(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": e.get("title"),
        "category": e.get("category"),
        "what": (e.get("description") or "")[:160],
        "address": e.get("address"),
        "lat": e.get("lat"),
        "lng": e.get("lng"),
        "free": e.get("isFree"),
        "walk_minutes_from_hostel": e.get("walkMinutes"),
        "tags": [t["tag"]["name"] for t in e.get("tags", []) if t.get("tag")],
    }


async def fetch_places(area: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    events = await _get_events(area, client)
    if not events:
        return {"area": area, "count": 0, "places": [], "note": "likelocal has no data for this area."}
    return {"area": area, "count": len(events), "places": [_place(e) for e in events[:MAX_PLACES]]}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


async def fetch_freshness(
    area: str, client: httpx.AsyncClient | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """likelocal stamps each place with lastCheckedAt; summarise those."""
    events = await _get_events(area, client)
    stamps = [_parse(e["lastCheckedAt"]) for e in events if e.get("lastCheckedAt")]
    if not stamps:
        return {"area": area, "count": len(events), "note": "No freshness data for this area."}
    now = now or datetime.now(timezone.utc)
    hours = lambda t: round((now - t).total_seconds() / 3600, 1)  # noqa: E731
    return {
        "area": area,
        "count": len(events),
        "newest_check": max(stamps).isoformat(),
        "oldest_check": min(stamps).isoformat(),
        "newest_age_hours": hours(max(stamps)),
        "oldest_age_hours": hours(min(stamps)),
    }
