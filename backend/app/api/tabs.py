"""Tab resource endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr
from ..schemas.models import TabCreate, TabMove, TabRename

router = APIRouter(prefix="/api/v1/tabs", tags=["tabs"])


@router.get("")
async def list_tabs(request: Request, workspace_id: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if workspace_id:
        params["workspace_id"] = workspace_id
    return await call_herdr(request, "tab.list", params)


@router.post("")
async def create_tab(request: Request, body: TabCreate) -> dict[str, Any]:
    return await call_herdr(request, "tab.create", body.model_dump(exclude_none=True))


@router.get("/{tab_id}")
async def get_tab(request: Request, tab_id: str) -> dict[str, Any]:
    return await call_herdr(request, "tab.get", {"tab_id": tab_id})


@router.patch("/{tab_id}")
async def rename_tab(request: Request, tab_id: str, body: TabRename) -> dict[str, Any]:
    return await call_herdr(
        request, "tab.rename", {"tab_id": tab_id, **body.model_dump(exclude_none=True)}
    )


@router.delete("/{tab_id}")
async def close_tab(request: Request, tab_id: str) -> dict[str, Any]:
    return await call_herdr(request, "tab.close", {"tab_id": tab_id})


@router.post("/{tab_id}/focus")
async def focus_tab(request: Request, tab_id: str) -> dict[str, Any]:
    return await call_herdr(request, "tab.focus", {"tab_id": tab_id})


@router.post("/{tab_id}/move")
async def move_tab(request: Request, tab_id: str, body: TabMove) -> dict[str, Any]:
    return await call_herdr(
        request, "tab.move", {"tab_id": tab_id, **body.model_dump(exclude_none=True)}
    )
