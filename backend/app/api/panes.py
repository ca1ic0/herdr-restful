"""Pane resource endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from ..deps import call_herdr
from ..schemas.models import (
    PaneFocusDirection,
    PaneMove,
    PaneRead,
    PaneRename,
    PaneReportAgent,
    PaneReportMetadata,
    PaneResize,
    PaneScroll,
    PaneSendInput,
    PaneSendKeys,
    PaneSendText,
    PaneSplit,
    PaneSwap,
    PaneWaitForOutput,
    PaneZoom,
)

router = APIRouter(prefix="/api/v1/panes", tags=["panes"])


@router.get("")
async def list_panes(
    request: Request,
    workspace_id: str | None = None,
    tab_id: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if workspace_id:
        params["workspace_id"] = workspace_id
    if tab_id:
        params["tab_id"] = tab_id
    return await call_herdr(request, "pane.list", params)


@router.get("/current")
async def current_pane(request: Request, caller_pane_id: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if caller_pane_id:
        params["caller_pane_id"] = caller_pane_id
    return await call_herdr(request, "pane.current", params)


@router.post("/split")
async def split_pane(request: Request, body: PaneSplit) -> dict[str, Any]:
    return await call_herdr(request, "pane.split", body.model_dump(exclude_none=True))


@router.post("/focus-direction")
async def focus_direction(request: Request, body: PaneFocusDirection) -> dict[str, Any]:
    return await call_herdr(request, "pane.focus_direction", body.model_dump(exclude_none=True))


@router.get("/{pane_id}")
async def get_pane(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.get", {"pane_id": pane_id})


@router.patch("/{pane_id}")
async def rename_pane(request: Request, pane_id: str, body: PaneRename) -> dict[str, Any]:
    params = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.rename", params)


@router.delete("/{pane_id}")
async def close_pane(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.close", {"pane_id": pane_id})


@router.post("/{pane_id}/focus")
async def focus_pane(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.focus", {"pane_id": pane_id})


@router.post("/{pane_id}/swap")
async def swap_pane(request: Request, pane_id: str, body: PaneSwap) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params.setdefault("pane_id", pane_id)
    return await call_herdr(request, "pane.swap", params)


@router.post("/{pane_id}/move")
async def move_pane(request: Request, pane_id: str, body: PaneMove) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.move", params)


@router.post("/{pane_id}/zoom")
async def zoom_pane(request: Request, pane_id: str, body: PaneZoom) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.zoom", params)


@router.post("/{pane_id}/resize")
async def resize_pane(request: Request, pane_id: str, body: PaneResize) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.resize", params)


@router.post("/{pane_id}/scroll")
async def scroll_pane(request: Request, pane_id: str, body: PaneScroll) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.scroll", params)


@router.get("/{pane_id}/layout")
async def pane_layout(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.layout", {"pane_id": pane_id})


@router.get("/{pane_id}/neighbor")
async def pane_neighbor(request: Request, pane_id: str, direction: str) -> dict[str, Any]:
    return await call_herdr(
        request, "pane.neighbor", {"pane_id": pane_id, "direction": direction}
    )


@router.get("/{pane_id}/edges")
async def pane_edges(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.edges", {"pane_id": pane_id})


@router.get("/{pane_id}/process-info")
async def pane_process_info(request: Request, pane_id: str) -> dict[str, Any]:
    return await call_herdr(request, "pane.process_info", {"pane_id": pane_id})


@router.get("/{pane_id}/output")
async def pane_output(
    request: Request,
    pane_id: str,
    source: str = "visible",
    lines: int | None = None,
    include_trailing_blank: bool | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"pane_id": pane_id, "source": source}
    if lines is not None:
        params["lines"] = lines
    if include_trailing_blank is not None:
        params["include_trailing_blank"] = include_trailing_blank
    return await call_herdr(request, "pane.read", params)


@router.post("/{pane_id}/output/read")
async def pane_read(request: Request, pane_id: str, body: PaneRead) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.read", params)


@router.post("/{pane_id}/input/text")
async def send_text(request: Request, pane_id: str, body: PaneSendText) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.send_text", params)


@router.post("/{pane_id}/input/keys")
async def send_keys(request: Request, pane_id: str, body: PaneSendKeys) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.send_keys", params)


@router.post("/{pane_id}/input")
async def send_input(request: Request, pane_id: str, body: PaneSendInput) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.send_input", params)


@router.post("/{pane_id}/wait-output")
async def wait_for_output(
    request: Request, pane_id: str, body: PaneWaitForOutput | None = None
) -> dict[str, Any]:
    params = (body.model_dump(exclude_none=True) if body else {})
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.wait_for_output", params)


@router.put("/{pane_id}/agent-status")
async def report_agent(request: Request, pane_id: str, body: PaneReportAgent) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.report_agent", params)


@router.put("/{pane_id}/metadata")
async def report_metadata(
    request: Request, pane_id: str, body: PaneReportMetadata
) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params["pane_id"] = pane_id
    return await call_herdr(request, "pane.report_metadata", params)
