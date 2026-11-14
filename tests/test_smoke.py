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


DAILY_MSG = "Route Buddy is resting for today. Try again tomorrow."


def _reset_limits(monkeypatch, daily, per_ip=100):
    from app import ratelimit
    monkeypatch.setattr(ratelimit, "LIMIT", per_ip)
    monkeypatch.setattr(ratelimit, "DAILY_LIMIT", daily)
    ratelimit._hits.clear()
    ratelimit._daily.clear()
    return ratelimit


def _post(c, ip):
    return c.post("/agent", json={}, headers={"x-forwarded-for": ip})


def test_daily_cap_across_ips(monkeypatch):
    _reset_limits(monkeypatch, 2)
    c = TestClient(app)
    assert _post(c, "1.1.1.1").status_code != 429
    assert _post(c, "2.2.2.2").status_code != 429
    r = _post(c, "3.3.3.3")
    assert r.status_code == 429 and r.json()["detail"] == DAILY_MSG
    assert c.get("/health").status_code == 200


def test_daily_zero_kill_switch(monkeypatch):
    _reset_limits(monkeypatch, 0)
    r = _post(TestClient(app), "1.1.1.1")
    assert r.status_code == 429 and r.json()["detail"] == DAILY_MSG


def test_ip_limited_requests_do_not_spend_daily(monkeypatch):
    rl = _reset_limits(monkeypatch, 5, per_ip=1)
    c = TestClient(app)
    codes = [_post(c, "1.1.1.1").status_code for _ in range(4)]
    assert codes[0] != 429 and codes[1:] == [429] * 3
    assert len(rl._daily) == 1


def test_daily_refusal_does_not_spend_ip_budget(monkeypatch):
    rl = _reset_limits(monkeypatch, 0)
    _post(TestClient(app), "1.1.1.1")
    assert len(rl._hits["1.1.1.1"]) == 0


def test_daily_window_rolls_over(monkeypatch):
    rl = _reset_limits(monkeypatch, 1)
    clock = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock[0])
    c = TestClient(app)
    assert _post(c, "1.1.1.1").status_code != 429
    assert _post(c, "2.2.2.2").status_code == 429
    clock[0] += rl.DAY + 1
    assert _post(c, "3.3.3.3").status_code != 429


def test_runs_per_day_env_parsing(monkeypatch):
    from app import ratelimit
    for raw, want in [("", 200), ("abc", 200), ("-3", 200), ("0", 0), ("7", 7)]:
        monkeypatch.setenv("RUNS_PER_DAY", raw)
        assert ratelimit._runs_per_day() == want
