"""Workspace resource endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from ..deps import call_herdr
from ..schemas.models import (
    WorkspaceClose,
    WorkspaceCreate,
    WorkspaceMove,
    WorkspaceMoveBlock,
    WorkspaceRename,
    WorkspaceReportMetadata,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(request: Request) -> dict[str, Any]:
    return await call_herdr(request, "workspace.list", {})


@router.post("")
async def create_workspace(request: Request, body: WorkspaceCreate) -> dict[str, Any]:
    return await call_herdr(request, "workspace.create", body.model_dump(exclude_none=True))


@router.post("/reorder")
async def reorder_workspaces(request: Request, body: WorkspaceMoveBlock) -> dict[str, Any]:
    """Atomically move an ordered block of workspaces (``workspace.move_block``)."""
    return await call_herdr(request, "workspace.move_block", body.model_dump(exclude_none=True))


@router.get("/{workspace_id}")
async def get_workspace(request: Request, workspace_id: str) -> dict[str, Any]:
    return await call_herdr(request, "workspace.get", {"workspace_id": workspace_id})


@router.patch("/{workspace_id}")
async def rename_workspace(
    request: Request, workspace_id: str, body: WorkspaceRename
) -> dict[str, Any]:
    params = {"workspace_id": workspace_id, **body.model_dump(exclude_none=True)}
    return await call_herdr(request, "workspace.rename", params)


@router.delete("/{workspace_id}")
async def close_workspace(
    request: Request, workspace_id: str, close_group: bool | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"workspace_id": workspace_id}
    if close_group is not None:
        params["close_group"] = close_group
    return await call_herdr(request, "workspace.close", params)


@router.post("/{workspace_id}/focus")
async def focus_workspace(request: Request, workspace_id: str) -> dict[str, Any]:
    return await call_herdr(request, "workspace.focus", {"workspace_id": workspace_id})


@router.post("/{workspace_id}/move")
async def move_workspace(
    request: Request, workspace_id: str, body: WorkspaceMove
) -> dict[str, Any]:
    params = {"workspace_id": workspace_id, **body.model_dump(exclude_none=True)}
    return await call_herdr(request, "workspace.move", params)


@router.put("/{workspace_id}/metadata")
async def report_workspace_metadata(
    request: Request, workspace_id: str, body: WorkspaceReportMetadata
) -> dict[str, Any]:
    params = {"workspace_id": workspace_id, **body.model_dump(exclude_none=True)}
    return await call_herdr(request, "workspace.report_metadata", params)
