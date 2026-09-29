"""An in-process fake herdr socket server for tests.

Mirrors the transport semantics verified against herdr 0.9.0:

* plain calls get exactly one request then the connection is closed
* ``events.subscribe`` keeps the connection open and can push events
* errors are ``{"id": ..., "error": {"code", "message"}}``
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], dict[str, Any]]

SAMPLE_WORKSPACES = [
    {
        "workspace_id": "w1",
        "number": 1,
        "label": "alpha",
        "focused": True,
        "pane_count": 2,
        "tab_count": 1,
        "active_tab_id": "w1:t1",
        "agent_status": "working",
    },
    {
        "workspace_id": "w2",
        "number": 2,
        "label": "beta",
        "focused": False,
        "pane_count": 1,
        "tab_count": 1,
        "active_tab_id": "w2:t1",
        "agent_status": "idle",
    },
]

SAMPLE_TABS = [
    {
        "tab_id": "w1:t1",
        "workspace_id": "w1",
        "number": 1,
        "label": "main",
        "focused": True,
        "pane_count": 2,
        "agent_status": "working",
    }
]

SAMPLE_PANES = [
    {
        "pane_id": "w1:p1",
        "terminal_id": "term_a",
        "workspace_id": "w1",
        "tab_id": "w1:t1",
        "focused": True,
        "agent_status": "working",
        "revision": 7,
        "cwd": "/repo",
    },
    {
        "pane_id": "w1:p2",
        "terminal_id": "term_b",
        "workspace_id": "w1",
        "tab_id": "w1:t1",
        "focused": False,
        "agent_status": "idle",
        "revision": 3,
        "cwd": "/repo/tests",
    },
]

SAMPLE_AGENTS = [
    {
        "terminal_id": "term_a",
        "agent": "claude",
        "agent_status": "working",
        "workspace_id": "w1",
        "tab_id": "w1:t1",
        "pane_id": "w1:p1",
        "focused": True,
        "revision": 7,
    }
]


def default_handler(request: dict[str, Any]) -> dict[str, Any]:
    method = request["method"]
    params = request.get("params") or {}

    if method == "ping":
        return {"type": "pong", "version": "0.9.0", "protocol": 22}

    if method == "session.snapshot":
        return {
            "type": "session_snapshot",
            "snapshot": {
                "version": "0.9.0",
                "protocol": 22,
                "focused_workspace_id": "w1",
                "focused_tab_id": "w1:t1",
                "focused_pane_id": "w1:p1",
                "workspaces": SAMPLE_WORKSPACES,
                "tabs": SAMPLE_TABS,
                "panes": SAMPLE_PANES,
                "layouts": [],
                "agents": SAMPLE_AGENTS,
            },
        }

    if method == "workspace.list":
        return {"type": "workspace_list", "workspaces": SAMPLE_WORKSPACES}

    if method == "workspace.get":
        for ws in SAMPLE_WORKSPACES:
            if ws["workspace_id"] == params.get("workspace_id"):
                return {"type": "workspace_info", "workspace": ws}
        return _err("workspace_not_found", f"workspace {params.get('workspace_id')} not found")

    if method == "workspace.create":
        ws = {
            "workspace_id": "wnew",
            "number": 3,
            "label": params.get("label") or "new",
            "focused": True,
            "pane_count": 1,
            "tab_count": 1,
            "active_tab_id": "wnew:t1",
            "agent_status": "unknown",
        }
        tab = {
            "tab_id": "wnew:t1",
            "workspace_id": "wnew",
            "number": 1,
            "label": "1",
            "focused": True,
            "pane_count": 1,
            "agent_status": "unknown",
        }
        pane = {
            "pane_id": "wnew:p1",
            "terminal_id": "term_new",
            "workspace_id": "wnew",
            "tab_id": "wnew:t1",
            "focused": True,
            "agent_status": "unknown",
            "revision": 1,
        }
        return {"type": "workspace_created", "workspace": ws, "tab": tab, "root_pane": pane}

    if method == "workspace.rename":
        return {
            "type": "workspace_info",
            "workspace": {**SAMPLE_WORKSPACES[0], "label": params.get("label")},
        }

    if method == "workspace.close":
        return {"type": "workspace_closed", "workspace_id": params.get("workspace_id")}

    if method == "workspace.focus":
        return {
            "type": "workspace_info",
            "workspace": {**SAMPLE_WORKSPACES[0], **params},
        }

    if method == "tab.list":
        return {"type": "tab_list", "tabs": SAMPLE_TABS}

    if method == "tab.get":
        for tab in SAMPLE_TABS:
            if tab["tab_id"] == params.get("tab_id"):
                return {"type": "tab_info", "tab": tab}
        return _err("tab_not_found", "tab not found")

    if method == "pane.list":
        return {"type": "pane_list", "panes": SAMPLE_PANES}

    if method == "pane.current":
        return {"type": "pane_current", "pane": SAMPLE_PANES[0]}

    if method == "pane.get":
        for pane in SAMPLE_PANES:
            if pane["pane_id"] == params.get("pane_id"):
                return {"type": "pane_info", "pane": pane}
        return _err("pane_not_found", "pane not found")

    if method == "pane.read":
        return {
            "type": "pane_read",
            "pane_id": params.get("pane_id"),
            "source": params.get("source", "visible"),
            "lines": ["$ echo hi", "hi", "$ "],
        }

    if method == "pane.send_text":
        return {"type": "pane_input_sent", "pane_id": params.get("pane_id") or "w1:p1"}

    if method == "pane.split":
        return {
            "type": "pane_created",
            "pane": {**SAMPLE_PANES[1], "pane_id": "w1:p3"},
            "layout": {"workspace_id": "w1", "tab_id": "w1:t1", "panes": [], "splits": []},
        }

    if method == "pane.zoom":
        return {
            "type": "pane_zoom",
            "changed": True,
            "zoom_changed": True,
            "focus_changed": False,
            "pane_id": params.get("pane_id") or "w1:p1",
            "focused_pane_id": "w1:p1",
            "zoomed": True,
            "layout": {"workspace_id": "w1", "tab_id": "w1:t1", "panes": [], "splits": []},
        }

    if method == "agent.list":
        return {"type": "agent_list", "agents": SAMPLE_AGENTS}

    if method == "agent.get":
        for agent in SAMPLE_AGENTS:
            if agent["pane_id"] == params.get("pane_id"):
                return {"type": "agent_info", "agent": agent}
        return _err("agent_not_found", "agent not found")

    if method == "layout.export":
        return {
            "type": "layout_export",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "zoomed": False,
            "focused_pane_id": "w1:p1",
            "root": {"type": "pane", "pane_id": "w1:p1"},
        }

    if method == "notification.show":
        return {"type": "notification_show", "shown": True, "reason": "shown"}

    if method == "integration.list":
        return {"type": "integration_list", "integrations": []}

    if method == "events.wait":
        return {
            "type": "event_wait_result",
            "matched": True,
            "event": params.get("match_event", {}).get("event"),
        }

    return _err("unknown_method", f"fake herdr has no handler for {method}")


def _err(code: str, message: str) -> dict[str, Any]:
    return {"__error__": {"code": code, "message": message}}


class FakeHerdrServer:
    """Asyncio unix-socket server implementing the fake protocol."""

    def __init__(self, socket_path: Path, handler: Handler | None = None):
        self.socket_path = Path(socket_path)
        self.handler = handler or default_handler
        self._server: asyncio.AbstractServer | None = None
        self.subscribers: list[asyncio.StreamWriter] = []
        self.requests: list[dict[str, Any]] = []
        self._handler_tasks: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle, path=str(self.socket_path)
        )

    async def stop(self) -> None:
        for writer in self.subscribers:
            try:
                writer.close()
            except Exception:
                pass
        self.subscribers.clear()
        for task in list(self._handler_tasks):
            task.cancel()
        if self._handler_tasks:
            await asyncio.gather(*self._handler_tasks, return_exceptions=True)
        self._handler_tasks.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.socket_path.exists():
            self.socket_path.unlink()

    async def wait_for_subscribers(self, count: int = 1, timeout: float = 5.0) -> None:
        """Wait until at least ``count`` live event subscribers are attached."""
        deadline = asyncio.get_running_loop().time() + timeout
        while len(self.subscribers) < count:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError(
                    f"only {len(self.subscribers)}/{count} herdr subscribers attached"
                )
            await asyncio.sleep(0.01)

    async def push_event(self, event: str, data: dict[str, Any]) -> None:
        """Push an event frame to every live subscriber."""
        frame = (json.dumps({"event": event, "data": data}) + "\n").encode("utf-8")
        for writer in list(self.subscribers):
            try:
                writer.write(frame)
                await writer.drain()
            except Exception:
                self.subscribers.remove(writer)

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._handler_tasks.add(task)
        try:
            line = await reader.readline()
            if not line:
                return
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": "",
                                "error": {"code": "invalid_request", "message": "bad json"},
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
                return

            self.requests.append(request)
            method = request.get("method")
            req_id = request.get("id", "")

            if method == "events.subscribe":
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": req_id,
                                "result": {
                                    "type": "subscribed",
                                    "subscriptions": (request.get("params") or {}).get(
                                        "subscriptions", []
                                    ),
                                },
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
                self.subscribers.append(writer)
                await reader.read()  # hold open until client disconnects
                return

            result = self.handler(request)
            if "__error__" in result:
                payload: dict[str, Any] = {"id": req_id, "error": result["__error__"]}
            else:
                payload = {"id": req_id, "result": result}
            writer.write((json.dumps(payload) + "\n").encode())
            await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            if task is not None:
                self._handler_tasks.discard(task)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
