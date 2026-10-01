"""Pi adapter.

Pi has no native unified approval dialog; permission prompts come from
extensions. Until a known extension's prompt shape is captured and tested,
this adapter recognises nothing (view + continue only).
"""

from __future__ import annotations

from .base import KIND_NONE, KIND_UNRECOGNIZED, PromptCard


class PiAdapter:
    agent_kind = "pi"

    def inspect(self, visible_lines: list[str], herdr_status: str) -> PromptCard:
        if herdr_status == "blocked":
            return PromptCard(
                kind=KIND_UNRECOGNIZED,
                summary="Pi 审批提示需要已知扩展适配",
            )
        return PromptCard(kind=KIND_NONE)

    def key_sequence(self, action: str, card: PromptCard) -> list[str] | None:
        return None
