"""Git worktree endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr
from ..schemas.models import WorktreeCreate, WorktreeOpen, WorktreeRemove

router = APIRouter(prefix="/api/v1", tags=["worktrees"])


@router.get("/worktrees")
async def list_worktrees(
    request: Request, workspace_id: str | None = None, cwd: str | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if workspace_id:
        params["workspace_id"] = workspace_id
    if cwd:
        params["cwd"] = cwd
    return await call_herdr(request, "worktree.list", params)


@router.post("/worktrees")
async def create_worktree(request: Request, body: WorktreeCreate) -> dict[str, Any]:
    return await call_herdr(request, "worktree.create", body.model_dump(exclude_none=True))


@router.post("/worktrees/open")
async def open_worktree(request: Request, body: WorktreeOpen) -> dict[str, Any]:
    return await call_herdr(request, "worktree.open", body.model_dump(exclude_none=True))


@router.delete("/worktrees/{workspace_id}")
async def remove_worktree(
    request: Request, workspace_id: str, force: bool | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"workspace_id": workspace_id}
    if force is not None:
        params["force"] = force
    return await call_herdr(request, "worktree.remove", params)
