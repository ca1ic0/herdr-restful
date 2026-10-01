"""Panel read model and action orchestration.

Read path: aggregate ``session.snapshot`` into bounded overview/detail
models, run the agent adapter on the live visible screen, and issue a
short-lived context token binding exactly what was shown.

Action path: deduplicate by request_id (persisted before sending), take a
per-terminal lock, re-read the live screen, and only send keys when the
fresh fingerprint matches the token — at most once, never auto-retried.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..herdr.client import HerdrClient
from ..herdr.errors import HerdrApiError, HerdrTransportError
from . import context as ctxmod
from .adapters import adapter_for
from .adapters.base import (
    ACT_CONTINUE,
    KIND_CONTINUATION,
    KIND_NONE,
    KIND_UNRECOGNIZED,
    PromptCard,
)
from .idempotency import ActionStore
from .events import PanelEventStore
from .view_models import (
    MAX_AGENTS,
    MAX_IMPACT_CHARS,
    MAX_LINE_CHARS,
    MAX_OUTPUT_LINES,
    MAX_SUMMARY_CHARS,
    ActionRequest,
    Detail,
    Overview,
    OverviewAgent,
    Pending,
)

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;?]*[A-Za-z]|\][^\x07]*\x07|.)")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

_DISPLAY_NAMES = {"claude": "Claude Code", "opencode": "OpenCode", "pi": "Pi"}


class PanelGone(Exception):
    """The terminal_id no longer resolves to a live agent/pane."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sanitize_line(line: str) -> str:
    line = _ANSI_RE.sub("", line)
    line = _CTRL_RE.sub("", line)
    return line.rstrip()[:MAX_LINE_CHARS]


def _body_hash(action: str, context_token: str, prompt: str | None) -> str:
    h = hashlib.sha256()
    h.update(action.encode("ascii"))
    h.update(b"|")
    h.update(context_token.encode("utf-8", "replace"))
    h.update(b"|")
    h.update((prompt or "").encode("utf-8", "replace"))
    return h.hexdigest()


class PanelService:
    def __init__(self, client: HerdrClient, store: ActionStore | None = None):
        self.client = client
        self.server_id = f"{socket.gethostname()}-boot-{uuid.uuid4().hex[:8]}"
        self.store = store or ActionStore(settings.resolve_panel_db_path())
        self.event_store = PanelEventStore(self.server_id)
        self._term_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    # ------------------------------------------------------------------
    # herdr helpers

    async def _snapshot(self) -> dict[str, Any]:
        result = await self.client.call("session.snapshot", {})
        snap = result.get("snapshot")
        if not isinstance(snap, dict):
            raise HerdrTransportError("session.snapshot returned no snapshot object")
        return snap

    async def _read_visible(self, pane_id: str) -> list[str]:
        """Bottom-of-screen lines for situation assessment (agent first).

        herdr 0.9.0 agent.* methods take ``target``; the payload carries a
        single ``read.text`` blob rather than a lines array. The ``lines``
        fallback keeps compatibility with older/simple responders.
        """
        try:
            result = await self.client.call(
                "agent.read", {"target": pane_id, "source": "visible"}
            )
        except HerdrApiError:
            result = await self.client.call(
                "pane.read", {"pane_id": pane_id, "source": "visible"}
            )
        read = result.get("read")
        if isinstance(read, dict) and isinstance(read.get("text"), str):
            return [sanitize_line(ln) for ln in read["text"].splitlines()]
        lines = result.get("lines")
        if isinstance(lines, list):
            return [sanitize_line(str(ln)) for ln in lines]
        return []

    # ------------------------------------------------------------------
    # overview

    async def overview(self) -> Overview:
        snap = await self._snapshot()
        panes = {p.get("terminal_id"): p for p in snap.get("panes") or []}
        workspaces = {w.get("workspace_id"): w for w in snap.get("workspaces") or []}
        now = _utcnow()

        agents: list[OverviewAgent] = []
        order = {p.get("terminal_id"): i for i, p in enumerate(snap.get("panes") or [])}
        for ag in snap.get("agents") or []:
            tid = ag.get("terminal_id")
            if not tid:
                continue  # without a stable id the device cannot act safely
            pane = panes.get(tid) or {}
            pane_id = ag.get("pane_id") or pane.get("pane_id") or ""
            kind = str(ag.get("agent") or "unknown")
            cwd = str(pane.get("cwd") or "")
            cwd_tail = cwd.rstrip("/").rsplit("/", 1)[-1] if cwd else ""
            ws = workspaces.get(ag.get("workspace_id")) or {}
            agents.append(
                OverviewAgent(
                    terminal_id=tid,
                    pane_id=pane_id,
                    agent=kind,
                    display_name=str(ag.get("display_name") or _DISPLAY_NAMES.get(kind, kind)),
                    workspace_label=str(ws.get("label") or ""),
                    cwd_tail=cwd_tail,
                    herdr_status=str(ag.get("agent_status") or "unknown"),
                    revision=int(ag.get("revision") or pane.get("revision") or 0),
                    updated_at=now,
                )
            )

        agents.sort(key=lambda a: order.get(a.terminal_id, 1 << 30))
        updated = self.event_store.observe(agents)
        for agent in agents:
            agent.updated_at = updated.get(agent.terminal_id, now)
        return Overview(
            server_id=self.server_id,
            snapshot_at=now,
            health="ok",
            total_count=len(agents),
            agents=agents[:MAX_AGENTS],
        )

    # ------------------------------------------------------------------
    # detail

    def _resolve(self, snap: dict[str, Any], terminal_id: str) -> tuple[dict, dict | None]:
        pane = next(
            (p for p in snap.get("panes") or [] if p.get("terminal_id") == terminal_id),
            None,
        )
        agent = next(
            (a for a in snap.get("agents") or [] if a.get("terminal_id") == terminal_id),
            None,
        )
        if pane is None and agent is None:
            raise PanelGone(terminal_id)
        return pane or {}, agent

    def _continuation_card(self, status: str) -> PromptCard:
        prompt = settings.panel_continue_prompt
        return PromptCard(
            kind=KIND_CONTINUATION,
            summary="Session idle; ready for a continue prompt",
            choices=[ACT_CONTINUE],
            source="new_prompt",
            evidence=[prompt],
            meta={"prompt": prompt},
        )

    def _build_pending(
        self,
        *,
        card: PromptCard,
        pane: dict[str, Any],
        agent_kind: str,
        terminal_id: str,
        pane_id: str,
    ) -> Pending:
        impact = card.impact
        if card.kind not in (KIND_NONE,) and not impact:
            cwd = str(pane.get("cwd") or pane_id)
            impact = f"Run in the terminal at {cwd}; applies this once"
        if len(card.summary) > MAX_SUMMARY_CHARS or len(impact) > MAX_IMPACT_CHARS:
            # never let a truncated card hide the impact of an action
            card = PromptCard(
                kind=KIND_UNRECOGNIZED,
                summary="Too long to confirm on the small screen",
                impact="",
                source="none",
            )

        pending = Pending(
            kind=card.kind if card.kind != KIND_NONE else "none",
            summary=card.summary,
            impact=impact,
            source=card.source,
            choices=list(card.choices),
            prompt=card.meta.get("prompt"),
        )
        if card.choices:
            fp_extra = card.meta.get("prompt") or ""
            pending.context_token = ctxmod.issue(
                ctxmod.PanelContext(
                    server_id=self.server_id,
                    terminal_id=terminal_id,
                    pane_id=pane_id,
                    agent=agent_kind,
                    fp=ctxmod.fingerprint(card.evidence, card.choices, fp_extra),
                    choices=list(card.choices),
                    expires_at=time.time() + settings.panel_context_ttl,
                )
            )
            pending.expires_at = datetime.fromtimestamp(
                time.time() + settings.panel_context_ttl, timezone.utc
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
        return pending

    def _inspect(self, agent_kind: str, status: str, lines: list[str]) -> PromptCard:
        adapter = adapter_for(agent_kind)
        card = adapter.inspect(lines, status) if adapter else PromptCard(kind=KIND_NONE)
        if card.kind == KIND_NONE:
            if status in ("idle", "done"):
                return self._continuation_card(status)
            if status == "blocked":
                return PromptCard(kind=KIND_UNRECOGNIZED, summary="Current prompt not recognized")
        return card

    async def detail(self, terminal_id: str) -> Detail:
        snap = await self._snapshot()
        pane, agent = self._resolve(snap, terminal_id)
        pane_id = str((agent or {}).get("pane_id") or pane.get("pane_id") or "")
        if not pane_id:
            raise PanelGone(terminal_id)
        agent_kind = str((agent or {}).get("agent") or "unknown")
        status = str((agent or {}).get("agent_status") or pane.get("agent_status") or "unknown")

        lines = await self._read_visible(pane_id)
        tail = [ln for ln in lines if ln.strip()][-MAX_OUTPUT_LINES:]
        card = self._inspect(agent_kind, status, lines)

        return Detail(
            server_id=self.server_id,
            terminal_id=terminal_id,
            pane_id=pane_id,
            agent=agent_kind,
            herdr_status=status,
            output_lines=tail,
            permission_mode=None,
            pending=self._build_pending(
                card=card,
                pane=pane,
                agent_kind=agent_kind,
                terminal_id=terminal_id,
                pane_id=pane_id,
            ),
        )

    # ------------------------------------------------------------------
    # actions

    async def _terminal_lock(self, terminal_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            return self._term_locks.setdefault(terminal_id, asyncio.Lock())

    async def execute_action(
        self, terminal_id: str, body: ActionRequest
    ) -> tuple[int, str, str]:
        """Run one action. Returns (http_status, result, message)."""
        bh = _body_hash(body.action, body.context_token, body.prompt)

        existing = await self.store.lookup(body.request_id)
        if existing is not None:
            if existing["body_hash"] != bh or existing["terminal_id"] != terminal_id:
                return 409, "id_conflict", "request_id reused with a different body"
            return _replay(existing["result"], existing["message"])

        try:
            ctx = ctxmod.verify(
                body.context_token, server_id=self.server_id, terminal_id=terminal_id
            )
        except ctxmod.ContextInvalid as exc:
            return 409, "stale_context", str(exc)

        # Persist before any key is sent: crash between insert and send still
        # counts as "uncertain" and is never silently re-sent on replay.
        if not await self.store.insert(body.request_id, terminal_id, bh):
            return 409, "id_conflict", "request_id already registered"
        await self.store.prune()

        async with await self._terminal_lock(terminal_id):
            try:
                status, result, message = await self._execute_locked(terminal_id, body, ctx)
            except HerdrTransportError as exc:
                logger.warning("action %s left uncertain: %s", body.request_id, exc)
                return 503, "offline", "herdr unreachable; result unknown"

        await self.store.set_result(body.request_id, result, message)
        return status, result, message

    async def _execute_locked(
        self, terminal_id: str, body: ActionRequest, ctx: ctxmod.PanelContext
    ) -> tuple[int, str, str]:
        snap = await self._snapshot()
        pane, agent = self._resolve(snap, terminal_id)
        pane_id = str((agent or {}).get("pane_id") or pane.get("pane_id") or "")
        agent_kind = str((agent or {}).get("agent") or "unknown")
        status = str((agent or {}).get("agent_status") or pane.get("agent_status") or "unknown")

        if pane_id != ctx.pane_id or agent_kind != ctx.agent:
            return 409, "stale_context", "terminal occupant changed"

        lines = await self._read_visible(pane_id)
        card = self._inspect(agent_kind, status, lines)
        fp_extra = card.meta.get("prompt") or ""
        fp = ctxmod.fingerprint(card.evidence, card.choices, fp_extra)
        if fp != ctx.fp:
            return 409, "stale_context", "prompt changed; review again"

        if body.action not in card.choices or body.action not in ctx.choices:
            return 422, "unsupported", "action not offered by the current prompt"

        if card.source == "new_prompt" and body.action == ACT_CONTINUE:
            prompt = card.meta.get("prompt") or settings.panel_continue_prompt
            if body.prompt is not None and body.prompt != prompt:
                return 409, "stale_context", "prompt text changed"
            await self.client.call(
                "agent.prompt", {"target": pane_id, "prompt": prompt, "submit": True}
            )
            return 200, "accepted", "continue prompt sent"

        adapter = adapter_for(agent_kind)
        keys = adapter.key_sequence(body.action, card) if adapter else None
        if not keys:
            return 422, "unsupported", "no verified key mapping for this action"
        await self.client.call("agent.send_keys", {"target": pane_id, "keys": keys})
        return 200, "accepted", f"sent {body.action}"


def _replay(result: str, message: str) -> tuple[int, str, str]:
    """Map a recorded result back to the fixed HTTP/result contract."""
    return {
        "accepted": (200, "accepted", message or "already sent"),
        "observed": (200, "observed", message),
        "stale_context": (409, "stale_context", message),
        "unsupported": (422, "unsupported", message),
    }.get(result, (200, "uncertain", message or "result unknown"))
