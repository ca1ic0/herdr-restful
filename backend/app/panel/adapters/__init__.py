"""Agent prompt adapters: recognise a CLI's visible approval UI.

Each adapter only supports prompt shapes it has tested screen samples for.
Anything incomplete, unknown-version or ambiguous must come back as
``kind="unrecognized"`` with empty choices — the panel then shows
"use host terminal" instead of guessing at keys.
"""

from __future__ import annotations

from .base import AgentPromptAdapter, PromptCard
from .claude import ClaudeAdapter
from .opencode import OpenCodeAdapter
from .pi import PiAdapter

_ADAPTERS: dict[str, AgentPromptAdapter] = {
    "claude": ClaudeAdapter(),
    "opencode": OpenCodeAdapter(),
    "pi": PiAdapter(),
}

__all__ = ["AgentPromptAdapter", "PromptCard", "adapter_for"]


def adapter_for(agent_kind: str) -> AgentPromptAdapter | None:
    return _ADAPTERS.get((agent_kind or "").lower())
