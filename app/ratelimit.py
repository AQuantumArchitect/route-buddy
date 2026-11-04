"""Tiny in-memory per-IP rate limit (fine for one Railway instance)."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

LIMIT = int(os.environ.get("RUNS_PER_IP_PER_HOUR", "10"))
WINDOW = 3600.0
_hits: dict[str, deque[float]] = defaultdict(deque)


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
    q.append(now)
