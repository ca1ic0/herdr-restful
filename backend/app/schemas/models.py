"""REST request models.

Response payloads are passed through from herdr verbatim so the wrapper does
not have to duplicate the (large) upstream schema. Request models are typed so
the OpenAPI document stays useful for callers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AgentStatus = Literal["idle", "working", "blocked", "done", "unknown"]
SplitDirection = Literal["right", "down"]
PaneDirection = Literal["left", "right", "up", "down"]
ReadSource = Literal["visible", "recent", "recent-unwrapped", "detection"]
WaitUntil = Literal["done", "blocked", "idle", "working", "unknown"]


# --- server / notification -------------------------------------------------


class NotificationShow(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None
    position: str | None = None
    sound: Literal["none", "done", "request"] | None = None


# --- workspace / tab -------------------------------------------------------


class WorkspaceCreate(BaseModel):
    cwd: str | None = None
    label: str | None = None
    focus: bool | None = None


class WorkspaceRename(BaseModel):
    label: str = Field(min_length=1)


class WorkspaceMove(BaseModel):
    insert_index: int = Field(ge=0)


class WorkspaceMoveBlock(BaseModel):
    workspace_ids: list[str] = Field(min_length=1)
    before_workspace_id: str | None = None


class WorkspaceClose(BaseModel):
    close_group: bool | None = None


class MetadataTokens(BaseModel):
    model_config = {"extra": "allow"}

    # token map is a free-form string -> str|null patch
    tokens: dict[str, str | None] = Field(default_factory=dict)
    ttl_ms: int | None = Field(default=None, ge=1, le=86_400_000)
    seq: int | None = Field(default=None, ge=0)


class WorkspaceReportMetadata(MetadataTokens):
    source: str = Field(min_length=1, max_length=80)


class TabCreate(BaseModel):
    workspace_id: str | None = None
    label: str | None = None
    focus: bool | None = None


class TabRename(BaseModel):
    label: str = Field(min_length=1)


class TabMove(BaseModel):
    insert_index: int = Field(ge=0)


# --- pane ------------------------------------------------------------------


class PaneSplit(BaseModel):
    pane_id: str | None = None
    direction: SplitDirection = "right"
    ratio: float | None = Field(default=None, gt=0, lt=1)
    cwd: str | None = None
    command: list[str] | None = None
    env: dict[str, str] | None = None
    label: str | None = None
    focus: bool | None = None


class PaneSwap(BaseModel):
    pane_id: str | None = None
    direction: PaneDirection | None = None
    source_pane_id: str | None = None
    target_pane_id: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> "PaneSwap":
        has_direction = self.direction is not None
        has_explicit = self.source_pane_id is not None or self.target_pane_id is not None
        if not has_direction and not has_explicit:
            raise ValueError("provide either direction or source_pane_id/target_pane_id")
        return self


class PaneMoveDestination(BaseModel):
    model_config = {"extra": "allow"}

    type: Literal["tab", "new_tab", "new_workspace"]
    tab_id: str | None = None
    target_pane_id: str | None = None
    split: SplitDirection | None = None
    ratio: float | None = None
    workspace_id: str | None = None
    label: str | None = None
    tab_label: str | None = None


class PaneMove(BaseModel):
    pane_id: str
    destination: PaneMoveDestination
    focus: bool | None = None


class PaneZoom(BaseModel):
    pane_id: str | None = None
    mode: Literal["toggle", "on", "off"] = "toggle"


class PaneResize(BaseModel):
    pane_id: str | None = None
    direction: PaneDirection
    amount: float = Field(gt=0)


class PaneFocusDirection(BaseModel):
    direction: PaneDirection
    caller_pane_id: str | None = None


class PaneRename(BaseModel):
    label: str | None = None
    title: str | None = None


class PaneSendText(BaseModel):
    pane_id: str | None = None
    text: str
    submit: bool | None = None


class PaneSendKeys(BaseModel):
    pane_id: str | None = None
    keys: list[str] = Field(min_length=1)


class PaneSendInput(BaseModel):
    pane_id: str | None = None
    text: str | None = None
    keys: list[str] | None = None
    submit: bool | None = None


class PaneRead(BaseModel):
    pane_id: str | None = None
    source: ReadSource = "visible"
    lines: int | None = Field(default=None, ge=1)
    include_trailing_blank: bool | None = None


class PaneScroll(BaseModel):
    pane_id: str | None = None
    offset_from_bottom: int | None = Field(default=None, ge=0)
    delta_rows: int | None = None


class PaneWaitForOutput(BaseModel):
    pane_id: str | None = None
    timeout_ms: int | None = Field(default=None, ge=1)
    idle_ms: int | None = Field(default=None, ge=1)
    match: str | None = None


class PaneReportAgent(BaseModel):
    pane_id: str | None = None
    source: str = Field(min_length=1, max_length=80)
    agent: str | None = None
    state: AgentStatus
    message: str | None = None
    state_labels: dict[str, str] | None = None
    ttl_ms: int | None = Field(default=None, ge=1, le=86_400_000)


class PaneReportMetadata(MetadataTokens):
    pane_id: str | None = None
    source: str = Field(min_length=1, max_length=80)
    agent: str | None = None
    applies_to_source: str | None = None
    title: str | None = None
    display_agent: str | None = None
    state_labels: dict[str, str] | None = None


# --- agent -----------------------------------------------------------------


class AgentStart(BaseModel):
    pane_id: str | None = None
    agent: str
    command: list[str] | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None


class AgentRename(BaseModel):
    name: str | None = None
    display_agent: str | None = None
    title: str | None = None


class AgentSendKeys(BaseModel):
    keys: list[str] = Field(min_length=1)


class AgentPrompt(BaseModel):
    prompt: str = Field(min_length=1)
    submit: bool | None = None
    wait: "AgentWait | None" = None


class AgentWait(BaseModel):
    until: WaitUntil = "done"
    timeout_ms: int | None = Field(default=None, ge=1)
    clear: bool | None = None


class AgentViewSet(BaseModel):
    source: str = Field(min_length=1, max_length=80)
    label: str | None = None
    filter: dict[str, Any] | None = None
    sort: list[dict[str, Any]] | None = None


class AgentViewClear(BaseModel):
    source: str | None = None


# --- layout / worktree -----------------------------------------------------


class LayoutExport(BaseModel):
    tab_id: str | None = None
    pane_id: str | None = None


class LayoutApply(BaseModel):
    workspace_id: str | None = None
    tab_id: str | None = None
    tab_label: str | None = None
    focus: bool | None = None
    root: dict[str, Any]


class LayoutSetSplitRatio(BaseModel):
    tab_id: str | None = None
    path: list[int] = Field(default_factory=list)
    ratio: float = Field(gt=0, lt=1)


class WorktreeCreate(BaseModel):
    workspace_id: str | None = None
    cwd: str | None = None
    branch: str | None = None
    base: str | None = None
    focus: bool | None = None


class WorktreeOpen(BaseModel):
    workspace_id: str | None = None
    cwd: str | None = None
    path: str | None = None
    branch: str | None = None
    focus: bool | None = None


class WorktreeRemove(BaseModel):
    force: bool | None = None


# --- events ----------------------------------------------------------------

# Subscription types use dotted names (``workspace.created``) while pushed
# event kinds use underscores (``workspace_created``). The pane-scoped
# subscriptions below additionally require a ``pane_id``.
SUBSCRIPTION_TYPE_ONLY: tuple[str, ...] = (
    "workspace.created",
    "workspace.updated",
    "workspace.metadata_updated",
    "workspace.renamed",
    "workspace.moved",
    "workspace.reordered",
    "workspace.closed",
    "workspace.focused",
    "worktree.created",
    "worktree.opened",
    "worktree.removed",
    "tab.created",
    "tab.closed",
    "tab.focused",
    "tab.renamed",
    "tab.moved",
    "pane.created",
    "pane.closed",
    "pane.updated",
    "pane.focused",
    "pane.moved",
    "pane.exited",
    "pane.agent_detected",
    "layout.updated",
)

SUBSCRIPTION_PANE_SCOPED: tuple[str, ...] = (
    "pane.agent_status_changed",
    "pane.scroll_changed",
    "pane.output_matched",
)


class EventSubscription(BaseModel):
    """One ``events.subscribe`` entry, forwarded to herdr as-is."""

    model_config = {"extra": "allow"}

    type: str
    pane_id: str | None = None
    workspace_id: str | None = None
    tab_id: str | None = None
    agent_status: AgentStatus | None = None


class EventMatch(BaseModel):
    """Matcher for ``events.wait``. Note the underscore event names here."""

    model_config = {"extra": "allow"}

    event: str
    workspace_id: str | None = None
    tab_id: str | None = None
    pane_id: str | None = None
    label: str | None = None
    agent_status: AgentStatus | None = None


class EventsWait(BaseModel):
    match_event: EventMatch
    timeout_ms: int | None = Field(default=None, ge=1)
