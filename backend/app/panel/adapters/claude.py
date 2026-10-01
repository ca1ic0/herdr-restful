"""Claude Code permission prompt adapter.

Supported shape (numbered option menu, current Claude Code TUI)::

    Bash command

      npm test

    Do you want to proceed?
    ❯ 1. Yes
      2. Yes, and don't ask again for npm commands in /repo
      3. No, and tell Claude what to do differently (esc)

and the legacy yes/no form::

    Allow? (y/n)

Number keys select menu options directly, so ``allow_once`` sends the number
of the plain "Yes" row, ``allow_always`` the "don't ask again" row and
``deny`` the "No" row. Everything else (questions, plan review, unknown
layouts) is reported unrecognized so the device offers no action.
"""

from __future__ import annotations

import re

from .base import (
    ACT_ALLOW_ALWAYS,
    ACT_ALLOW_ONCE,
    ACT_DENY,
    KIND_APPROVAL,
    KIND_NONE,
    KIND_UNRECOGNIZED,
    PromptCard,
)

_QUESTION = "Do you want to proceed?"
_OPTION_RE = re.compile(r"^\s*[❯>]?\s*(\d)\.\s+(.+?)\s*$")
_YN_RE = re.compile(r"\ballow\b.*\((y/n|yes/no)\)", re.IGNORECASE)
_BORDER_RE = re.compile(r"^[╭╮╰╯│─┌┐└┘├┤\s]*$")

_MAX_SUMMARY_CHARS = 120


def _clean(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        ln = ln.strip().strip("│").strip()
        if ln and not _BORDER_RE.match(ln):
            out.append(ln)
    return out


class ClaudeAdapter:
    agent_kind = "claude"

    def inspect(self, visible_lines: list[str], herdr_status: str) -> PromptCard:
        lines = _clean(visible_lines)
        for i, ln in enumerate(lines):
            if _QUESTION in ln:
                return self._numbered(lines, i)
        for ln in lines:
            if _YN_RE.search(ln):
                return self._yes_no(lines, ln)
        return PromptCard(kind=KIND_NONE)

    # -- numbered option menu -------------------------------------------

    def _numbered(self, lines: list[str], q_idx: int) -> PromptCard:
        options: dict[str, tuple[str, str]] = {}  # action -> (number, label)
        for ln in lines[q_idx + 1 :]:
            m = _OPTION_RE.match(ln)
            if not m:
                if options:  # option block ended
                    break
                continue
            num, label = m.group(1), m.group(2)
            low = label.lower()
            if low.startswith("yes") and "don" in low and "ask" in low:
                options.setdefault(ACT_ALLOW_ALWAYS, (num, label))
            elif low.startswith("yes"):
                options.setdefault(ACT_ALLOW_ONCE, (num, label))
            elif low.startswith("no"):
                options.setdefault(ACT_DENY, (num, label))

        if ACT_ALLOW_ONCE not in options or ACT_DENY not in options:
            return PromptCard(
                kind=KIND_UNRECOGNIZED,
                summary="Claude 提示选项无法完整识别",
                evidence=[lines[q_idx]],
                meta={"style": "numbered"},
            )

        subject = self._subject(lines[:q_idx])
        choices = [ACT_ALLOW_ONCE, ACT_DENY]
        if ACT_ALLOW_ALWAYS in options:
            choices.insert(1, ACT_ALLOW_ALWAYS)
        evidence = [lines[q_idx]] + [f"{n}. {lbl}" for n, lbl in (options[a] for a in choices)]
        if subject:
            evidence.insert(0, subject)
        return PromptCard(
            kind=KIND_APPROVAL,
            summary=subject or "Claude 请求许可",
            choices=choices,
            source="terminal_ui",
            evidence=evidence,
            meta={"style": "numbered", "keys": {a: n for a, (n, _) in options.items()}},
        )

    @staticmethod
    def _subject(before: list[str]) -> str:
        """Best-effort one-line description of what is being approved."""
        skip = ("do you want", "esc to", "tab to")
        cand = [ln for ln in before if not any(s in ln.lower() for s in skip)]
        if not cand:
            return ""
        text = " / ".join(cand[-2:])
        return text[:_MAX_SUMMARY_CHARS]

    # -- legacy y/n ------------------------------------------------------

    def _yes_no(self, lines: list[str], question: str) -> PromptCard:
        subject = self._subject(lines[: lines.index(question)] if question in lines else lines)
        evidence = ([subject] if subject else []) + [question]
        return PromptCard(
            kind=KIND_APPROVAL,
            summary=subject or "Claude 请求许可",
            choices=[ACT_ALLOW_ONCE, ACT_DENY],
            source="terminal_ui",
            evidence=evidence,
            meta={"style": "yn", "keys": {ACT_ALLOW_ONCE: "y", ACT_DENY: "n"}},
        )

    # -- execution --------------------------------------------------------

    def key_sequence(self, action: str, card: PromptCard) -> list[str] | None:
        key = (card.meta.get("keys") or {}).get(action)
        return [key] if key else None
