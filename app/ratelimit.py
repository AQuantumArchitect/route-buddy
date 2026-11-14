"""Tiny in-memory rate limits: per-IP hourly and global daily (fine for one Railway instance)."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

LIMIT = int(os.environ.get("RUNS_PER_IP_PER_HOUR", "10"))
WINDOW = 3600.0
_hits: dict[str, deque[float]] = defaultdict(deque)

DAY = 86400.0
DEFAULT_RUNS_PER_DAY = 200


def _runs_per_day() -> int:
    try:
        n = int(os.environ.get("RUNS_PER_DAY", ""))
    except ValueError:
        return DEFAULT_RUNS_PER_DAY
    return n if n >= 0 else DEFAULT_RUNS_PER_DAY


DAILY_LIMIT = _runs_per_day()  # 0 refuses every run (kill switch)
_daily: deque[float] = deque()


def client_ip(request: Request) -> str:
    # Railway's proxy appends the real client IP last; earlier entries are client-supplied.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request) -> None:
    ip, now = client_ip(request), time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, f"Demo limit: {LIMIT} runs per hour per IP. Try again later.")
    while _daily and now - _daily[0] > DAY:
        _daily.popleft()
    if len(_daily) >= DAILY_LIMIT:
        raise HTTPException(429, "Route Buddy is resting for today. Try again tomorrow.")
    # Record only once both checks pass, so a refused request never spends the other budget.
    q.append(now)
    _daily.append(now)
