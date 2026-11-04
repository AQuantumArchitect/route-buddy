import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import likelocal
from app.main import app

EVENT = {
    "title": "Midnight Cowboy Speakeasy", "category": "nightlife", "description": "A bar.",
    "address": "313 E 6th St", "lat": 30.26, "lng": -97.74, "isFree": False, "walkMinutes": 3,
    "tags": [{"tag": {"name": "Chill"}}], "lastCheckedAt": "2026-11-04T00:56:22.818Z",
}


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_index_served():
    assert "Route Buddy" in TestClient(app).get("/").text


@pytest.mark.asyncio
@respx.mock
async def test_find_places_mocked():
    route = respx.get(f"{likelocal.BASE_URL}/api/events", params={"city": "austin"}).mock(
        return_value=httpx.Response(200, json=[EVENT])
    )
    out = await likelocal.fetch_places("Austin")
    assert route.called
    assert out["count"] == 1 and out["places"][0]["name"] == "Midnight Cowboy Speakeasy"
    assert out["places"][0]["tags"] == ["Chill"]


@pytest.mark.asyncio
@respx.mock
async def test_check_freshness_mocked():
    respx.get(f"{likelocal.BASE_URL}/api/events").mock(return_value=httpx.Response(200, json=[EVENT]))
    from datetime import datetime, timezone
    out = await likelocal.fetch_freshness("austin", now=datetime(2026, 11, 4, 2, 56, 22, tzinfo=timezone.utc))
    assert out["newest_age_hours"] == 2.0


def test_rate_limit(monkeypatch):
    from app import ratelimit
    monkeypatch.setattr(ratelimit, "LIMIT", 2)
    ratelimit._hits.clear()
    c = TestClient(app)
    # Invalid bodies still pass through the rate-limit dependency first.
    codes = [c.post("/agent", json={}).status_code for _ in range(3)]
    assert codes[-1] == 429 and 429 not in codes[:2]
    ratelimit._hits.clear()
