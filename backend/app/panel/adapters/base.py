"""Adapter interface shared by all CLI prompt parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Pending card kinds returned to the device (see PRODUCT_LOGIC §4.2).
KIND_APPROVAL = "approval"
KIND_QUESTION = "question"
KIND_CONTINUATION = "continuation"
KIND_UNRECOGNIZED = "unrecognized"
KIND_NONE = "none"

# Semantic actions the panel understands.
ACT_ALLOW_ONCE = "allow_once"
ACT_ALLOW_ALWAYS = "allow_always"
ACT_DENY = "deny"
ACT_CONTINUE = "continue"


@dataclass
class PromptCard:
    """What the adapter recognised on the visible screen."""

    kind: str = KIND_NONE
    summary: str = ""
    impact: str = ""
    choices: list[str] = field(default_factory=list)
    source: str = "none"  # terminal_ui | new_prompt | none
    evidence: list[str] = field(default_factory=list)  # lines the fingerprint binds
    meta: dict = field(default_factory=dict)  # adapter-private execution data


class AgentPromptAdapter(Protocol):
    """Parse a CLI's visible prompt UI and map semantic actions to keys."""

    agent_kind: str

    def inspect(self, visible_lines: list[str], herdr_status: str) -> PromptCard:
        """Recognise the current prompt. Never guess: unrecognized beats wrong."""
        ...

    def key_sequence(self, action: str, card: PromptCard) -> list[str] | None:
        """Keys for one herdr ``agent.send_keys`` call, or None if unmappable."""
        ...
