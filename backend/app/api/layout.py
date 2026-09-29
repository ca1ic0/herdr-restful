"""Layout export/apply endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr
from ..schemas.models import LayoutApply, LayoutExport, LayoutSetSplitRatio

router = APIRouter(prefix="/api/v1/layout", tags=["layout"])


@router.get("/export")
async def export_layout(
    request: Request, tab_id: str | None = None, pane_id: str | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if tab_id:
        params["tab_id"] = tab_id
    if pane_id:
        params["pane_id"] = pane_id
    return await call_herdr(request, "layout.export", params)


@router.post("/apply")
async def apply_layout(request: Request, body: LayoutApply) -> dict[str, Any]:
    return await call_herdr(request, "layout.apply", body.model_dump(exclude_none=True))


@router.patch("/split-ratio")
async def set_split_ratio(request: Request, body: LayoutSetSplitRatio) -> dict[str, Any]:
    return await call_herdr(request, "layout.set_split_ratio", body.model_dump(exclude_none=True))
