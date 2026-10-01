"""Bounded, versioned response models for the device panel API.

These mirror the fixed-size structures in the firmware (``panel_model.h``):
overview <= 24 cards, detail output <= 12 lines, one pending card. Anything
longer is truncated host-side and, where truncation would hide impact, the
choices list is emptied instead.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

MAX_AGENTS = 24
MAX_OUTPUT_LINES = 12
MAX_LINE_CHARS = 96
MAX_SUMMARY_CHARS = 150
MAX_IMPACT_CHARS = 150

Action = Literal["allow_once", "allow_always", "deny", "continue"]
PendingKind = Literal["approval", "question", "continuation", "unrecognized", "none"]


class OverviewAgent(BaseModel):
    terminal_id: str
    pane_id: str
    agent: str
    display_name: str
    workspace_label: str
    cwd_tail: str
    herdr_status: str
    revision: int = 0
    updated_at: str


class Overview(BaseModel):
    schema_version: int = SCHEMA_VERSION
    server_id: str
    snapshot_at: str
    health: Literal["ok", "degraded"]
    total_count: int
    agents: list[OverviewAgent] = Field(default_factory=list)


class Pending(BaseModel):
    kind: PendingKind = "none"
    summary: str = ""
    impact: str = ""
    source: str = "none"  # terminal_ui | new_prompt | none
    choices: list[Action] = Field(default_factory=list)
    context_token: str = ""
    expires_at: str = ""
    prompt: str | None = None


class Detail(BaseModel):
    schema_version: int = SCHEMA_VERSION
    server_id: str
    terminal_id: str
    pane_id: str
    agent: str
    herdr_status: str
    output_lines: list[str] = Field(default_factory=list)
    permission_mode: str | None = None  # v1 never proves a mode -> null
    pending: Pending = Field(default_factory=Pending)


class ActionRequest(BaseModel):
    action: Action
    context_token: str = Field(min_length=1, max_length=1024)
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    prompt: str | None = Field(default=None, max_length=512)


class ActionResponse(BaseModel):
    schema_version: int = SCHEMA_VERSION
    request_id: str
    result: str  # accepted | uncertain | stale_context | id_conflict | unsupported | offline
    message: str = ""
