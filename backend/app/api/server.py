"""Server lifecycle and capability endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr

router = APIRouter(prefix="/api/v1/server", tags=["server"])


@router.get("")
@router.get("/")
async def server_info(request: Request) -> dict[str, Any]:
    """Server handshake: version, protocol and capabilities (``ping``)."""
    return await call_herdr(request, "ping", {})


@router.post("/stop")
async def stop_server(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "server.stop", {})


@router.post("/reload-config")
async def reload_config(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "server.reload_config", {})


@router.get("/agent-manifests")
async def agent_manifests(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "server.agent_manifests", {})


@router.post("/agent-manifests/reload")
async def reload_agent_manifests(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "server.reload_agent_manifests", {})
