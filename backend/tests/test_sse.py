"""SSE bridge tests against a real uvicorn server.

httpx ``ASGITransport`` awaits full app completion, so an unbounded SSE stream
deadlocks it. These tests therefore run the app under ``uvicorn``.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from .fake_herdr import FakeHerdrServer


async def test_sse_open_frame_then_event(live_server: str, fake_herdr: FakeHerdrServer) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream("GET", f"{live_server}/api/v1/events") as res:
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/event-stream")

            lines: list[str] = []

            async def collect() -> None:
                async for line in res.aiter_lines():
                    if line and not line.startswith(":"):
                        lines.append(line)
                    if len(lines) >= 2:  # bridge.open + its data frame
                        break

            await asyncio.wait_for(collect(), timeout=10.0)

    assert lines[0] == "event: bridge.open"
    subs = json.loads(lines[1].removeprefix("data: "))["subscriptions"]
    # default scope is every subscription that needs no extra fields
    assert {"type": "workspace.created"} in subs
    assert {"type": "pane.updated"} in subs
    assert {"type": "layout.updated"} in subs
    assert all("pane_id" not in s for s in subs)


async def test_sse_delivers_pushed_events(live_server: str, fake_herdr: FakeHerdrServer) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream("GET", f"{live_server}/api/v1/events") as res:
            got: list[str] = []
            started = asyncio.Event()

            async def collect() -> None:
                async for line in res.aiter_lines():
                    if line and not line.startswith(":"):
                        got.append(line)
                        if line == "event: bridge.open":
                            started.set()
                    if len(got) >= 4:
                        break

            task = asyncio.create_task(collect())
            await asyncio.wait_for(started.wait(), timeout=10.0)
            await fake_herdr.wait_for_subscribers(1)
            await fake_herdr.push_event(
                "pane_agent_status_changed",
                {
                    "type": "pane_agent_status_changed",
                    "pane_id": "w1:p1",
                    "workspace_id": "w1",
                    "agent_status": "done",
                },
            )
            await asyncio.wait_for(task, timeout=10.0)

    joined = "\n".join(got)
    assert "event: pane_agent_status_changed" in joined
    payload_line = next(
        g for g in got if g.startswith("data: ") and "pane_agent_status_changed" in g
    )
    payload = json.loads(payload_line.removeprefix("data: "))
    assert payload["data"]["agent_status"] == "done"


async def test_sse_filtered_subscription(live_server: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream(
            "GET",
            f"{live_server}/api/v1/events",
            params={"types": "workspace.focused,pane.focused"},
        ) as res:
            lines: list[str] = []

            async def collect() -> None:
                async for line in res.aiter_lines():
                    if line and not line.startswith(":"):
                        lines.append(line)
                    if len(lines) >= 2:
                        break

            await asyncio.wait_for(collect(), timeout=10.0)

    assert lines[0] == "event: bridge.open"
    subs = json.loads(lines[1].removeprefix("data: "))["subscriptions"]
    assert subs == [{"type": "workspace.focused"}, {"type": "pane.focused"}]


async def test_sse_validation_errors(live_server: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{live_server}/api/v1/events", params={"types": "nope.nope"})
        assert res.status_code == 400
        assert res.json()["detail"]["error"]["code"] == "invalid_params"

        res = await client.get(
            f"{live_server}/api/v1/events", params={"types": "pane.agent_status_changed"}
        )
        assert res.status_code == 400
        assert "pane_id is required" in res.json()["detail"]["error"]["message"]


async def test_sse_pane_scoped_with_pane_id(live_server: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream(
            "GET",
            f"{live_server}/api/v1/events",
            params={"types": "pane.agent_status_changed", "pane_id": "w1:p1"},
        ) as res:
            lines: list[str] = []

            async def collect() -> None:
                async for line in res.aiter_lines():
                    if line and not line.startswith(":"):
                        lines.append(line)
                    if len(lines) >= 2:
                        break

            await asyncio.wait_for(collect(), timeout=10.0)

    subs = json.loads(lines[1].removeprefix("data: "))["subscriptions"]
    assert subs == [{"type": "pane.agent_status_changed", "pane_id": "w1:p1"}]


@pytest.mark.parametrize("path", ["/api/v1/events?types=workspace.created"])
async def test_sse_keepalive_comment(live_server: str, path: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream("GET", f"{live_server}{path}") as res:
            saw_keepalive = False

            async def collect() -> None:
                nonlocal saw_keepalive
                async for line in res.aiter_lines():
                    if line.startswith(":"):
                        saw_keepalive = True
                        break

            await asyncio.wait_for(collect(), timeout=10.0)

    assert saw_keepalive
