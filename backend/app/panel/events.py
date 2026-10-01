"""Bounded, cursor-based panel sound events derived from agent transitions.

The Herdr socket API does not expose the desktop client's exact sound play
decision. These events are explicitly marked ``state_transition``. A process
restart changes PanelService.server_id, so old cursors cannot be replayed.
"""

from __future__ import annotations

import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

CURSOR_RE = re.compile(r"^evt-([0-9a-f]{16})$")
MAX_EVENTS = 256
MAX_AGE_SECONDS = 600


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class PanelEventStore:
    def __init__(self, server_id: str):
        self.server_id = server_id
        self._sequence = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._previous: dict[str, tuple[str, str]] = {}
        self._updated_at: dict[str, str] = {}

    @staticmethod
    def _cursor(sequence: int) -> str:
        return f"evt-{sequence:016x}"

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0]["_mono"] > MAX_AGE_SECONDS:
            self._events.popleft()

    def observe(self, agents: list[Any]) -> dict[str, str]:
        """Observe one successful full snapshot; first sight never notifies."""
        now_mono = time.monotonic()
        now_utc = _utcnow()
        latest: dict[str, tuple[str, str]] = {}
        for agent in agents:
            tid, kind, status = agent.terminal_id, agent.agent, agent.herdr_status
            latest[tid] = (kind, status)
            previous = self._previous.get(tid)
            if previous is None or previous[0] != kind:
                self._updated_at[tid] = now_utc
                continue
            old_status = previous[1]
            if old_status == status:
                continue
            self._updated_at[tid] = now_utc
            sound: str | None = None
            if status == "blocked" and old_status in {"working", "idle", "done"}:
                sound = "request"
            elif old_status == "working" and status == "done":
                sound = "done"
            if sound is not None:
                self._sequence += 1
                self._events.append(
                    {
                        "event_id": self._cursor(self._sequence),
                        "terminal_id": tid,
                        "agent": kind,
                        "kind": sound,
                        "source": "state_transition",
                        "occurred_at": now_utc,
                        "_mono": now_mono,
                        "_sequence": self._sequence,
                    }
                )
        self._previous = latest
        self._updated_at = {
            tid: self._updated_at[tid] for tid in latest if tid in self._updated_at
        }
        self._prune(now_mono)
        return dict(self._updated_at)

    def page(self, after: str | None, limit: int) -> dict[str, Any]:
        if not 1 <= limit <= 16:
            raise ValueError("limit must be 1..16")
        now = time.monotonic()
        self._prune(now)
        latest = self._cursor(self._sequence)
        if after is None:
            return self._response(latest, latest, False, False, [])
        match = CURSOR_RE.fullmatch(after)
        if match is None:
            raise ValueError("invalid cursor")
        seq = int(match.group(1), 16)
        if seq > self._sequence:
            raise ValueError("cursor is ahead of server")
        if (self._events and seq < self._events[0]["_sequence"] - 1) or (
            not self._events and seq < self._sequence
        ):
            return self._response(latest, latest, True, False, [])
        items = [e for e in self._events if e["_sequence"] > seq]
        chosen = items[:limit]
        next_cursor = chosen[-1]["event_id"] if chosen else after
        public = [
            {
                k: v for k, v in event.items() if not k.startswith("_")
            }
            | {"age_ms": max(0, int((now - event["_mono"]) * 1000))}
            for event in chosen
        ]
        return self._response(latest, next_cursor, False, len(items) > limit, public)

    def _response(
        self, latest: str, next_cursor: str, gap: bool,
        has_more: bool, events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "server_id": self.server_id,
            "latest_cursor": latest,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "gap": gap,
            "events": events,
        }
