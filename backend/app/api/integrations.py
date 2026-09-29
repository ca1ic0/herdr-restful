"""Built-in integration management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


@router.get("")
async def list_integrations(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "integration.list", {})


@router.post("")
async def install_integration(request: Request, target: str) -> dict[str, Any]:
    return await call_herdr(request, "integration.install", {"target": target})


@router.delete("/{target}")
async def uninstall_integration(request: Request, target: str) -> dict[str, Any]:
    return await call_herdr(request, "integration.uninstall", {"target": target})
