from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from .fake_herdr import SAMPLE_AGENTS, SAMPLE_PANES, SAMPLE_WORKSPACES


async def test_health(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["herdr"]["type"] == "pong"


async def test_server_info(client: AsyncClient) -> None:
    res = await client.get("/api/v1/server")
    assert res.status_code == 200
    assert res.json()["type"] == "pong"


async def test_session_snapshot(client: AsyncClient) -> None:
    res = await client.get("/api/v1/session/snapshot")
    assert res.status_code == 200
    snap = res.json()["snapshot"]
    assert snap["focused_workspace_id"] == "w1"
    assert len(snap["workspaces"]) == len(SAMPLE_WORKSPACES)


async def test_workspace_list(client: AsyncClient) -> None:
    res = await client.get("/api/v1/workspaces")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "workspace_list"
    assert [w["workspace_id"] for w in body["workspaces"]] == ["w1", "w2"]


async def test_workspace_get(client: AsyncClient) -> None:
    res = await client.get("/api/v1/workspaces/w1")
    assert res.status_code == 200
    assert res.json()["workspace"]["label"] == "alpha"


async def test_workspace_get_missing_is_404(client: AsyncClient) -> None:
    res = await client.get("/api/v1/workspaces/nope")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["error"]["code"] == "workspace_not_found"


async def test_workspace_create(client: AsyncClient) -> None:
    res = await client.post("/api/v1/workspaces", json={"label": "gamma"})
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "workspace_created"
    assert body["workspace"]["label"] == "gamma"
    assert body["root_pane"]["pane_id"] == "wnew:p1"


async def test_workspace_rename(client: AsyncClient) -> None:
    res = await client.patch("/api/v1/workspaces/w1", json={"label": "renamed"})
    assert res.status_code == 200
    assert res.json()["workspace"]["label"] == "renamed"


async def test_workspace_close(client: AsyncClient) -> None:
    res = await client.delete("/api/v1/workspaces/w2", params={"close_group": True})
    assert res.status_code == 200
    assert res.json()["workspace_id"] == "w2"


async def test_workspace_focus(client: AsyncClient) -> None:
    res = await client.post("/api/v1/workspaces/w2/focus")
    assert res.status_code == 200
    assert res.json()["type"] == "workspace_info"


async def test_tab_list_and_get(client: AsyncClient) -> None:
    res = await client.get("/api/v1/tabs")
    assert res.status_code == 200
    assert res.json()["tabs"][0]["tab_id"] == "w1:t1"

    res = await client.get("/api/v1/tabs/w1:t1")
    assert res.status_code == 200
    assert res.json()["tab"]["workspace_id"] == "w1"


async def test_pane_list_and_get(client: AsyncClient) -> None:
    res = await client.get("/api/v1/panes")
    assert res.status_code == 200
    assert len(res.json()["panes"]) == len(SAMPLE_PANES)

    res = await client.get("/api/v1/panes/w1:p1")
    assert res.status_code == 200
    assert res.json()["pane"]["terminal_id"] == "term_a"


async def test_pane_current(client: AsyncClient) -> None:
    res = await client.get("/api/v1/panes/current")
    assert res.status_code == 200
    assert res.json()["pane"]["pane_id"] == "w1:p1"


async def test_pane_output(client: AsyncClient) -> None:
    res = await client.get("/api/v1/panes/w1:p1/output", params={"source": "recent", "lines": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "pane_read"
    assert body["lines"][-1] == "$ "


async def test_pane_send_text(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/panes/w1:p1/input/text", json={"text": "ls", "submit": True}
    )
    assert res.status_code == 200
    assert res.json()["type"] == "pane_input_sent"


async def test_pane_split_and_zoom(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/panes/split", json={"pane_id": "w1:p1", "direction": "right", "ratio": 0.5}
    )
    assert res.status_code == 200
    assert res.json()["pane"]["pane_id"] == "w1:p3"

    res = await client.post("/api/v1/panes/w1:p1/zoom", json={"mode": "on"})
    assert res.status_code == 200
    assert res.json()["zoomed"] is True


async def test_pane_zoom_rejects_unknown_mode(client: AsyncClient) -> None:
    res = await client.post("/api/v1/panes/w1:p1/zoom", json={"mode": "sideways"})
    assert res.status_code == 422


async def test_agent_list_and_get(client: AsyncClient) -> None:
    res = await client.get("/api/v1/agents")
    assert res.status_code == 200
    assert res.json()["agents"][0]["agent"] == "claude"

    res = await client.get("/api/v1/agents/w1:p1")
    assert res.status_code == 200
    assert res.json()["agent"]["agent_status"] == "working"

    assert SAMPLE_AGENTS[0]["pane_id"] == "w1:p1"


async def test_agent_missing_is_404(client: AsyncClient) -> None:
    res = await client.get("/api/v1/agents/w9:p9")
    assert res.status_code == 404
    assert res.json()["detail"]["error"]["code"] == "agent_not_found"


async def test_layout_export(client: AsyncClient) -> None:
    res = await client.get("/api/v1/layout/export", params={"tab_id": "w1:t1"})
    assert res.status_code == 200
    assert res.json()["root"]["type"] == "pane"


async def test_notification_show(client: AsyncClient) -> None:
    res = await client.post("/api/v1/notifications", json={"title": "hello"})
    assert res.status_code == 200
    assert res.json() == {"type": "notification_show", "shown": True, "reason": "shown"}


async def test_notification_requires_title(client: AsyncClient) -> None:
    res = await client.post("/api/v1/notifications", json={"body": "no title"})
    assert res.status_code == 422


async def test_events_wait(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/events/wait",
        json={"match_event": {"event": "workspace_focused", "workspace_id": "w1"}},
    )
    assert res.status_code == 200
    assert res.json()["matched"] is True


async def test_sse_rejects_unknown_type(client: AsyncClient) -> None:
    res = await client.get("/api/v1/events", params={"types": "not.a.type"})
    assert res.status_code == 400
    assert res.json()["detail"]["error"]["code"] == "invalid_params"


async def test_sse_pane_scoped_requires_pane_id(client: AsyncClient) -> None:
    res = await client.get("/api/v1/events", params={"types": "pane.agent_status_changed"})
    assert res.status_code == 400
    assert "pane_id is required" in res.json()["detail"]["error"]["message"]


async def test_herdr_unavailable_maps_to_503(fake_herdr) -> None:
    from httpx import ASGITransport, AsyncClient as AC

    from app.config import settings
    from app.main import create_app

    await fake_herdr.stop()
    settings.socket_path = str(fake_herdr.socket_path)
    application = create_app()
    try:
        async with application.router.lifespan_context(application):
            transport = ASGITransport(app=application)
            async with AC(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/workspaces")
                assert res.status_code == 503
                assert res.json()["detail"]["error"]["code"] == "herdr_unavailable"
    finally:
        settings.socket_path = None
