"""Server-Sent Events bridge over herdr ``events.subscribe``.

Two naming conventions coexist upstream and are preserved here:

* subscription request ``type`` uses dotted names (``workspace.created``)
* pushed event kind uses underscores (``workspace_created``)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..config import settings
from ..deps import call_herdr, get_client
from ..herdr.errors import HerdrTransportError
from ..schemas.models import (
    SUBSCRIPTION_PANE_SCOPED,
    SUBSCRIPTION_TYPE_ONLY,
    EventsWait,
)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

ALL_SUBSCRIPTIONS = set(SUBSCRIPTION_TYPE_ONLY) | set(SUBSCRIPTION_PANE_SCOPED)


def _build_subscriptions(
    types: list[str] | None,
    pane_id: str | None,
    workspace_id: str | None,
    tab_id: str | None,
    agent_status: str | None,
) -> list[dict[str, Any]]:
    """Translate query filters into herdr subscription descriptors.

    When ``types`` is omitted the default is the full set of subscriptions that
    need no extra fields, which is what a dashboard wants. Pane-scoped
    subscriptions (``pane.agent_status_changed`` and friends) require a
    ``pane_id`` upstream, so one must be supplied for those.
    """
    chosen = types if types else list(SUBSCRIPTION_TYPE_ONLY)
    unknown = [t for t in chosen if t not in ALL_SUBSCRIPTIONS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_params",
                    "message": f"unknown subscription type(s): {', '.join(unknown)}",
                    "data": {"known": sorted(ALL_SUBSCRIPTIONS)},
                }
            },
        )

    pane_scoped = [t for t in chosen if t in SUBSCRIPTION_PANE_SCOPED]
    if pane_scoped and not pane_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_params",
                    "message": (
                        "pane_id is required for pane-scoped subscriptions: "
                        + ", ".join(pane_scoped)
                    ),
                }
            },
        )

    extra: dict[str, Any] = {}
    if pane_id:
        extra["pane_id"] = pane_id
    if workspace_id:
        extra["workspace_id"] = workspace_id
    if tab_id:
        extra["tab_id"] = tab_id
    if agent_status:
        extra["agent_status"] = agent_status

    return [{"type": t, **extra} for t in chosen]


def _sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    lines = [f"event: {event}"]
    for chunk in payload.split("\n"):
        lines.append(f"data: {chunk}")
    return "\n".join(lines) + "\n\n"


@router.get("")
async def stream_events(
    request: Request,
    types: str | None = Query(
        default=None,
        description=(
            "Comma separated herdr subscription types using dotted names "
            "(e.g. `workspace.created,pane.updated`). Defaults to the full "
            "set of subscriptions that need no extra fields."
        ),
    ),
    pane_id: str | None = Query(default=None, description="Required for pane-scoped types"),
    workspace_id: str | None = None,
    tab_id: str | None = None,
    agent_status: str | None = None,
) -> StreamingResponse:
    """Stream herdr events as Server-Sent Events.

    The first frame is `event: bridge.open`; upstream events follow as
    `event: <event_kind>` with the herdr event envelope as JSON data. A
    `: keepalive` comment is emitted when no event arrives within the
    heartbeat interval.
    """
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    subscriptions = _build_subscriptions(
        type_list, pane_id, workspace_id, tab_id, agent_status
    )
    client = get_client(request)
    heartbeat = settings.sse_heartbeat

    async def event_generator():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        stop = asyncio.Event()
        subscribed = asyncio.Event()

        def mark_subscribed() -> None:
            subscribed.set()

        async def pump() -> None:
            try:
                async for msg in client.subscribe(subscriptions, on_subscribed=mark_subscribed):
                    if stop.is_set():
                        return
                    await queue.put(msg)
            except HerdrTransportError as exc:
                await queue.put({"event": "bridge.error", "data": {"message": str(exc)}})
            except asyncio.CancelledError:
                raise
            finally:
                await queue.put(None)

        task = asyncio.create_task(pump())
        try:
            # Do not claim the bridge is open until herdr acknowledged the
            # subscription, otherwise early events can be missed by clients.
            try:
                await asyncio.wait_for(subscribed.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                yield _sse(
                    "bridge.error",
                    {"message": "timed out waiting for herdr subscription ack"},
                )
                return
            yield _sse("bridge.open", {"subscriptions": subscriptions})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if msg is None:
                    break
                event_name = msg.get("event") or "message"
                yield _sse(str(event_name), msg)
        finally:
            stop.set()
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/wait")
async def wait_for_event(request: Request, body: EventsWait) -> dict[str, Any]:
    """One-shot wait for a matching event (``events.wait``)."""
    return await call_herdr(request, "events.wait", body.model_dump(exclude_none=True))
