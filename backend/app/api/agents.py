"""Agent resource endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr
from ..schemas.models import (
    AgentPrompt,
    AgentRename,
    AgentSendKeys,
    AgentStart,
    AgentViewClear,
    AgentViewSet,
    AgentWait,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("")
async def list_agents(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "agent.list", {})


@router.put("/view")
async def set_view(request: Request, body: AgentViewSet) -> dict[str, Any]:
    return await call_herdr(request, "agent.view.set", body.model_dump(exclude_none=True))


@router.delete("/view")
async def clear_view(request: Request, body: AgentViewClear | None = None) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True) if body else {}
    return await call_herdr(request, "agent.view.clear", params)


@router.post("/start")
async def start_agent(request: Request, body: AgentStart) -> dict[str, Any]:
    return await call_herdr(request, "agent.start", body.model_dump(exclude_none=True))


@router.get("/{pane_id}")
async def get_agent(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "agent.get", {"pane_id": pane_id})


@router.patch("/{pane_id}")
async def rename_agent(request: Request, pane_id: str, body: AgentRename) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "agent.rename", params)


@router.get("/{pane_id}/output")
async def read_agent(
    request: Request,
    pane_id: str,
    source: str = "visible",
    lines: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"pane_id": pane_id, "source": source}
    if lines is not None:
        params["lines"] = lines
    return await call_herdr(request, "agent.read", params)


@router.get("/{pane_id}/explain")
async def explain_agent(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "agent.explain", {"target": pane_id})


@router.post("/{pane_id}/keys")
async def agent_keys(request: Request, pane_id: str, body: AgentSendKeys) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "agent.send_keys", params)


@router.post("/{pane_id}/prompt")
async def prompt_agent(request: Request, pane_id: str, body: AgentPrompt) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "agent.prompt", params)


@router.post("/{pane_id}/wait")
async def wait_agent(request: Request, pane_id: str, body: AgentWait | None = None) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True) if body else {}
    params["pane_id"] = pane_id
    return await call_herdr(request, "agent.wait", params)


@router.post("/{pane_id}/focus")
async def focus_agent(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "agent.focus", {"pane_id": pane_id})
