"""OpenCode permission adapter.

No verified screen samples exist yet, so this adapter deliberately
recognises nothing: it returns ``unrecognized`` for any blocked screen and
the device will show "use host terminal". Add real captured screens plus
tests before enabling any key mapping here — never ship a guessed mapping.
"""

from __future__ import annotations

from .base import KIND_NONE, KIND_UNRECOGNIZED, PromptCard


class OpenCodeAdapter:
    agent_kind = "opencode"

    def inspect(self, visible_lines: list[str], herdr_status: str) -> PromptCard:
        if herdr_status == "blocked":
            return PromptCard(
                kind=KIND_UNRECOGNIZED,
                summary="OpenCode 提示尚未适配",
            )
        return PromptCard(kind=KIND_NONE)

    def key_sequence(self, action: str, card: PromptCard) -> list[str] | None:
        return None
