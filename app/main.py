from __future__ import annotations

from pathlib import Path

from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse

from .agent import build_agent
from .ratelimit import rate_limit

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Route Buddy")

add_agent_framework_fastapi_endpoint(
    app, build_agent(), "/agent", dependencies=[Depends(rate_limit)], single_user=True
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
