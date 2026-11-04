"""The Route Buddy agent: one MAF Agent, Claude Haiku, three tools, shared-state route."""

from __future__ import annotations

import os
from typing import Annotated, Any

from agent_framework import Agent, tool
from agent_framework.ag_ui import AgentFrameworkAgent
from agent_framework.anthropic import AnthropicClient
from pydantic import BaseModel, Field

from . import likelocal

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_TOKENS = int(os.environ.get("MAX_TOKENS_PER_RUN", "1024"))

INSTRUCTIONS = """You are Route Buddy, a friendly walking-route planner.

1. Call find_places for the area the user names (a city slug like austin, or a ZIP).
2. Optionally call check_freshness and mention how fresh the data is, in one short line.
3. Pick 3-5 stops that make a fun, walkable route. Call update_route with the COMPLETE ordered
   list of stops (name, a short reason, and lat/lng if known). Always send the full list.
4. Reply in 1-3 short sentences. Only use places returned by find_places. If the area has
   no data, say so and suggest austin or portland."""


class Stop(BaseModel):
    name: str = Field(..., description="Place name, exactly as returned by find_places")
    reason: str = Field(..., description="One short sentence on why it's on the route")
    lat: float | None = None
    lng: float | None = None


@tool
async def find_places(area: Annotated[str, "City/area slug (e.g. austin, portland) or ZIP code"]) -> dict[str, Any]:
    """Find walkable places in an area from likelocal's public data."""
    try:
        return await likelocal.fetch_places(area)
    except Exception as exc:  # let the model recover gracefully
        return {"error": f"likelocal request failed: {type(exc).__name__}"}


@tool
async def check_freshness(area: Annotated[str, "City/area slug or ZIP code"]) -> dict[str, Any]:
    """Report how recently likelocal checked the data for an area."""
    try:
        return await likelocal.fetch_freshness(area)
    except Exception as exc:
        return {"error": f"likelocal request failed: {type(exc).__name__}"}


@tool
def update_route(stops: list[Stop]) -> str:
    """Set the route shown to the user: the complete ordered list of stops, each with a reason."""
    return "Route updated."


def build_agent(client: Any | None = None) -> AgentFrameworkAgent:
    client = client or AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL)
    agent = Agent(
        name="route_buddy",
        instructions=INSTRUCTIONS,
        client=client,
        tools=[find_places, check_freshness, update_route],
        default_options={"max_tokens": MAX_TOKENS},
    )
    return AgentFrameworkAgent(
        agent=agent,
        name="RouteBuddy",
        description="Plans a short, fun walking route from likelocal data",
        state_schema={"route": {"type": "array", "description": "Ordered route stops with reasons"}},
        predict_state_config={"route": {"tool": "update_route", "tool_argument": "stops"}},
        require_confirmation=False,
    )
