"""Tests for the /api/v1/panel device gateway.

The fake herdr serves a configurable world: one claude agent on a pane whose
visible screen and status the test can mutate between calls. send_keys and
agent.prompt calls are recorded so tests can assert at-most-once semantics.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.panel.auth import reset_auth_backoff

from .fake_herdr import default_handler

DEVICE = {"Authorization": "Bearer test-device-token"}

CLAUDE_APPROVAL_SCREEN = [
    "╭──────────────────────────────────────────────╮",
    "│ Bash command                                 │",
    "│                                              │",
    "│   npm test                                   │",
    "│                                              │",
    "│ Do you want to proceed?                      │",
    "│ ❯ 1. Yes                                     │",
    "│   2. Yes, and don't ask again for npm test   │",
    "│   3. No, and tell Claude what to do          │",
    "╰──────────────────────────────────────────────╯",
]

IDLE_SCREEN = ["$ claude", "Ready for input", ""]


def make_world() -> dict[str, Any]:
    return {
        "status": "blocked",
        "screen": list(CLAUDE_APPROVAL_SCREEN),
        "sent_keys": [],
        "sent_prompts": [],
    }


def panel_handler(world: dict[str, Any]):
    def handler(request: dict[str, Any]) -> dict[str, Any]:
        method = request["method"]
        params = request.get("params") or {}

        if method == "session.snapshot":
            return {
                "type": "session_snapshot",
                "snapshot": {
                    "version": "0.9.0",
                    "protocol": 22,
                    "workspaces": [
                        {"workspace_id": "w1", "number": 1, "label": "api"},
                    ],
                    "tabs": [],
                    "panes": [
                        {
                            "pane_id": "w1:p1",
                            "terminal_id": "term_a",
                            "workspace_id": "w1",
                            "tab_id": "w1:t1",
                            "revision": 7,
                            "cwd": "/repo/project-api",
                            "agent_status": world["status"],
                        },
                    ],
                    "layouts": [],
                    "agents": [
                        {
                            "terminal_id": "term_a",
                            "agent": "claude",
                            "agent_status": world["status"],
                            "workspace_id": "w1",
                            "tab_id": "w1:t1",
                            "pane_id": "w1:p1",
                            "revision": 7,
                        },
                    ],
                },
            }

        if method == "agent.read":
            # live herdr 0.9.0 shape: target param, single read.text blob
            assert "target" in params
            return {
                "type": "pane_read",
                "read": {
                    "pane_id": params["target"],
                    "source": params.get("source", "visible"),
                    "format": "text",
                    "text": "\n".join(world["screen"]),
                },
            }

        if method == "agent.send_keys":
            world["sent_keys"].append(list(params.get("keys") or []))
            return {"type": "agent_keys_sent", "pane_id": params.get("pane_id")}

        if method == "agent.prompt":
            world["sent_prompts"].append(params.get("prompt"))
            return {"type": "agent_prompt_sent", "pane_id": params.get("pane_id")}

        return default_handler(request)

    return handler


@pytest.fixture
def world() -> dict[str, Any]:
    return make_world()


@pytest.fixture
async def panel_client(client, fake_herdr, world, tmp_path, monkeypatch):
    fake_herdr.handler = panel_handler(world)
    monkeypatch.setattr(settings, "panel_tokens", "test-device-token")
    monkeypatch.setattr(settings, "panel_db_path", str(tmp_path / "panel.db"))
    reset_auth_backoff()
    yield client
    reset_auth_backoff()


async def test_requires_auth(panel_client):
    r = await panel_client.get("/api/v1/panel/overview")
    assert r.status_code == 401
    r = await panel_client.get(
        "/api/v1/panel/overview", headers={"Authorization": "Bearer wrong"}
    )
    assert r.status_code == 401


async def test_short_code_normalisation(panel_client, monkeypatch):
    """Pairing codes compare case- and separator-insensitively."""
    monkeypatch.setattr(settings, "panel_tokens", "K7QX-2M9T-W4HB")
    for typed in ("K7QX-2M9T-W4HB", "k7qx-2m9t-w4hb", "k7qx2m9tw4hb", "K7QX 2M9T W4HB"):
        r = await panel_client.get(
            "/api/v1/panel/overview", headers={"Authorization": f"Bearer {typed}"}
        )
        assert r.status_code == 200, typed


async def test_auth_backoff_rate_limits(panel_client):
    bad = {"Authorization": "Bearer wrong"}
    assert (await panel_client.get("/api/v1/panel/overview", headers=bad)).status_code == 401
    # backoff is active after the first wrong-token failure: next request
    # is rejected with 429 even if it carries the correct token
    r = await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    assert r.status_code == 429


async def test_overview_shape(panel_client):
    r = await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == 1
    assert body["health"] == "ok"
    assert body["server_id"]
    assert body["total_count"] == 1
    (ag,) = body["agents"]
    assert ag["terminal_id"] == "term_a"
    assert ag["pane_id"] == "w1:p1"
    assert ag["agent"] == "claude"
    assert ag["display_name"] == "Claude Code"
    assert ag["workspace_label"] == "api"
    assert ag["cwd_tail"] == "project-api"
    assert ag["herdr_status"] == "blocked"


async def test_sound_events_baseline_transitions_and_no_replay(panel_client, world):
    first = (await panel_client.get("/api/v1/panel/events", headers=DEVICE)).json()
    assert first["events"] == []
    assert first["next_cursor"] == first["latest_cursor"]
    cursor = first["next_cursor"]

    # First observation of an already blocked agent must be silent.
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    r = await panel_client.get(f"/api/v1/panel/events?after={cursor}", headers=DEVICE)
    assert r.json()["events"] == []

    world["status"] = "working"
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    world["status"] = "blocked"
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    r = await panel_client.get(f"/api/v1/panel/events?after={cursor}", headers=DEVICE)
    body = r.json()
    assert [e["kind"] for e in body["events"]] == ["request"]
    assert body["events"][0]["source"] == "state_transition"
    assert body["events"][0]["age_ms"] >= 0

    cursor = body["next_cursor"]
    world["status"] = "working"
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    world["status"] = "done"
    await panel_client.get("/api/v1/panel/overview", headers=DEVICE)
    r = await panel_client.get(f"/api/v1/panel/events?after={cursor}", headers=DEVICE)
    assert [e["kind"] for e in r.json()["events"]] == ["done"]
    assert (await panel_client.get("/api/v1/panel/events", headers=DEVICE)).json()["events"] == []


async def test_sound_events_requires_auth(panel_client):
    assert (await panel_client.get("/api/v1/panel/events")).status_code == 401


async def test_detail_approval_card(panel_client):
    r = await panel_client.get("/api/v1/panel/agents/term_a", headers=DEVICE)
    assert r.status_code == 200
    body = r.json()
    assert body["herdr_status"] == "blocked"
    assert body["permission_mode"] is None
    assert len(body["output_lines"]) <= 12
    pending = body["pending"]
    assert pending["kind"] == "approval"
    assert "npm test" in pending["summary"]
    assert pending["choices"] == ["allow_once", "allow_always", "deny"]
    assert pending["context_token"]
    assert pending["expires_at"]


async def test_detail_unknown_terminal_404(panel_client):
    r = await panel_client.get("/api/v1/panel/agents/nope", headers=DEVICE)
    assert r.status_code == 404


async def _detail_token(client) -> str:
    r = await client.get("/api/v1/panel/agents/term_a", headers=DEVICE)
    return r.json()["pending"]["context_token"]


async def test_action_allow_once_sends_exactly_one_key(panel_client, world):
    token = await _detail_token(panel_client)
    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "allow_once", "context_token": token, "request_id": "req-0001"},
    )
    assert r.status_code == 200
    assert r.json()["result"] == "accepted"
    assert world["sent_keys"] == [["1"]]


async def test_action_replay_returns_recorded_result(panel_client, world):
    token = await _detail_token(panel_client)
    payload = {"action": "deny", "context_token": token, "request_id": "req-0002"}
    r1 = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions", headers=DEVICE, json=payload
    )
    r2 = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions", headers=DEVICE, json=payload
    )
    assert r1.status_code == 200 and r1.json()["result"] == "accepted"
    assert r2.status_code == 200 and r2.json()["result"] == "accepted"
    assert world["sent_keys"] == [["3"]]  # exactly once


async def test_action_id_conflict(panel_client):
    token = await _detail_token(panel_client)
    await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "deny", "context_token": token, "request_id": "req-0003"},
    )
    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "allow_once", "context_token": token, "request_id": "req-0003"},
    )
    assert r.status_code == 409
    assert r.json()["result"] == "id_conflict"


async def test_action_stale_after_screen_change(panel_client, world):
    token = await _detail_token(panel_client)
    world["screen"] = ["something else entirely", ""]
    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "allow_once", "context_token": token, "request_id": "req-0004"},
    )
    assert r.status_code == 409
    assert r.json()["result"] == "stale_context"
    assert world["sent_keys"] == []


async def test_action_expired_context(panel_client, monkeypatch):
    monkeypatch.setattr(settings, "panel_context_ttl", -1.0)
    token = await _detail_token(panel_client)
    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "allow_once", "context_token": token, "request_id": "req-0005"},
    )
    assert r.status_code == 409
    assert r.json()["result"] == "stale_context"


async def test_action_unsupported_choice(panel_client):
    token = await _detail_token(panel_client)
    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={"action": "continue", "context_token": token, "request_id": "req-0006"},
    )
    assert r.status_code == 422
    assert r.json()["result"] == "unsupported"


async def test_idle_agent_offers_continue(panel_client, world):
    world["status"] = "idle"
    world["screen"] = list(IDLE_SCREEN)
    r = await panel_client.get("/api/v1/panel/agents/term_a", headers=DEVICE)
    pending = r.json()["pending"]
    assert pending["kind"] == "continuation"
    assert pending["choices"] == ["continue"]
    assert pending["source"] == "new_prompt"
    assert pending["prompt"]

    r = await panel_client.post(
        "/api/v1/panel/agents/term_a/actions",
        headers=DEVICE,
        json={
            "action": "continue",
            "context_token": pending["context_token"],
            "request_id": "req-0007",
            "prompt": pending["prompt"],
        },
    )
    assert r.status_code == 200
    assert r.json()["result"] == "accepted"
    assert world["sent_prompts"] == [pending["prompt"]]
    assert world["sent_keys"] == []


async def test_unrecognized_screen_offers_no_choices(panel_client, world):
    world["screen"] = [" Applying edits…", ""]
    r = await panel_client.get("/api/v1/panel/agents/term_a", headers=DEVICE)
    pending = r.json()["pending"]
    assert pending["kind"] == "unrecognized"
    assert pending["choices"] == []
    assert pending["context_token"] == ""
