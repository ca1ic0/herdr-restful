"""/api/v1/panel routes: authenticated, bounded device API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Query
from fastapi.responses import JSONResponse

from ..herdr.errors import HerdrTransportError
from .auth import require_device
from .service import PanelGone, PanelService
from .view_models import ActionRequest, ActionResponse

router = APIRouter(
    prefix="/api/v1/panel",
    tags=["panel"],
    dependencies=[Depends(require_device)],
)


def get_panel_service(request: Request) -> PanelService:
    service = getattr(request.app.state, "panel", None)
    if service is None:
        from ..deps import get_client

        service = PanelService(get_client(request))
        request.app.state.panel = service
    return service


@router.get("/overview")
async def overview(request: Request):
    service = get_panel_service(request)
    try:
        return await service.overview()
    except HerdrTransportError as exc:
        raise _offline_http(exc) from exc


@router.get("/events")
async def sound_events(
    request: Request,
    after: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=16, ge=1, le=16),
):
    service = get_panel_service(request)
    try:
        return service.event_store.page(after, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents/{terminal_id}")
async def detail(request: Request, terminal_id: str):
    service = get_panel_service(request)
    try:
        return await service.detail(terminal_id)
    except PanelGone:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "gone", "message": "session ended"}},
        )
    except HerdrTransportError as exc:
        raise _offline_http(exc) from exc


@router.post("/agents/{terminal_id}/actions")
async def action(request: Request, terminal_id: str, body: ActionRequest):
    service = get_panel_service(request)
    try:
        status, result, message = await service.execute_action(terminal_id, body)
    except PanelGone:
        status, result, message = 409, "stale_context", "session ended"
    except HerdrTransportError:
        status, result, message = 503, "offline", "herdr unreachable; result unknown"
    return JSONResponse(
        status_code=status,
        content=ActionResponse(
            request_id=body.request_id, result=result, message=message
        ).model_dump(),
    )


def _offline_http(exc: HerdrTransportError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": {"code": "herdr_unavailable", "message": str(exc)}},
    )
