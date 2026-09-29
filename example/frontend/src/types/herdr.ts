/**
 * Types mirroring the herdr socket API schema (protocol 22, herdr 0.9.0).
 *
 * Responses from the REST wrapper are the herdr `result` objects verbatim, so
 * these shapes are the wire contract.
 */

export type AgentStatus = "idle" | "working" | "blocked" | "done" | "unknown";

export type SplitDirection = "right" | "down";
export type PaneDirection = "left" | "right" | "up" | "down";
export type ReadSource = "visible" | "recent" | "recent-unwrapped" | "detection";

export interface WorkspaceWorktreeInfo {
  branch?: string | null;
  path?: string | null;
  [k: string]: unknown;
}

export interface WorkspaceInfo {
  workspace_id: string;
  number: number;
  label: string;
  focused: boolean;
  pane_count: number;
  tab_count: number;
  active_tab_id: string;
  agent_status: AgentStatus;
  tokens?: Record<string, string>;
  worktree?: WorkspaceWorktreeInfo | null;
}

export interface TabInfo {
  tab_id: string;
  workspace_id: string;
  number: number;
  label: string;
  focused: boolean;
  pane_count: number;
  agent_status: AgentStatus;
}

export interface PaneScrollInfo {
  offset_from_bottom: number;
  max_offset_from_bottom: number;
  viewport_rows: number;
}

export interface AgentSessionInfo {
  source: string;
  agent: string;
  kind: "id" | "path";
  value: string;
}

export interface PaneInfo {
  pane_id: string;
  terminal_id: string;
  workspace_id: string;
  tab_id: string;
  focused: boolean;
  agent_status: AgentStatus;
  revision: number;
  agent?: string | null;
  display_agent?: string | null;
  title?: string | null;
  label?: string | null;
  cwd?: string | null;
  foreground_cwd?: string | null;
  terminal_title?: string | null;
  terminal_title_stripped?: string | null;
  scroll?: PaneScrollInfo | null;
  state_labels?: Record<string, string>;
  tokens?: Record<string, string>;
  agent_session?: AgentSessionInfo | null;
}

export interface AgentInfo {
  terminal_id: string;
  agent_status: AgentStatus;
  workspace_id: string;
  tab_id: string;
  pane_id: string;
  focused: boolean;
  revision: number;
  agent?: string | null;
  display_agent?: string | null;
  name?: string | null;
  title?: string | null;
  cwd?: string | null;
  foreground_cwd?: string | null;
  state_change_seq?: number;
  interactive_ready?: boolean;
  launch_pending?: boolean;
  screen_detection_skipped?: boolean;
  state_labels?: Record<string, string>;
  tokens?: Record<string, string>;
  agent_session?: AgentSessionInfo | null;
  terminal_title?: string | null;
  terminal_title_stripped?: string | null;
}

export interface PaneLayoutRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PaneLayoutPane {
  pane_id: string;
  focused: boolean;
  rect: PaneLayoutRect;
}

export interface PaneLayoutSplit {
  direction: SplitDirection;
  ratio: number;
  rect: PaneLayoutRect;
}

export interface PaneLayoutSnapshot {
  workspace_id: string;
  tab_id: string;
  zoomed: boolean;
  area: PaneLayoutRect;
  focused_pane_id: string;
  panes: PaneLayoutPane[];
  splits: PaneLayoutSplit[];
}

export interface SessionSnapshot {
  version: string;
  protocol: number;
  focused_workspace_id?: string;
  focused_tab_id?: string;
  focused_pane_id?: string;
  workspaces: WorkspaceInfo[];
  tabs: TabInfo[];
  panes: PaneInfo[];
  layouts?: PaneLayoutSnapshot[];
  agents?: AgentInfo[];
}

export interface ServerCapabilities {
  live_handoff?: boolean;
  detached_server_daemon?: boolean;
  endpoint_protocol_generation?: number;
  surface_interest?: boolean;
  health_check?: boolean;
}

export interface PongResult {
  type: "pong";
  version: string;
  protocol: number;
  capabilities?: ServerCapabilities | null;
}

export interface SessionSnapshotResult {
  type: "session_snapshot";
  snapshot: SessionSnapshot;
}

export interface PaneReadResult {
  type: string;
  pane_id?: string;
  source?: string;
  lines?: string[];
  text?: string;
  [k: string]: unknown;
}

export interface WorkspaceListResult {
  type: "workspace_list";
  workspaces: WorkspaceInfo[];
}

export interface TabListResult {
  type: "tab_list";
  tabs: TabInfo[];
}

export interface PaneListResult {
  type: "pane_list";
  panes: PaneInfo[];
}

export interface AgentListResult {
  type: "agent_list";
  agents: AgentInfo[];
}

/** Envelope pushed on the SSE bridge for every herdr event. */
export interface HerdrEventEnvelope {
  event: HerdrEventKind;
  data: Record<string, unknown> & { type: string };
}

export type HerdrEventKind =
  | "workspace_created"
  | "workspace_updated"
  | "workspace_metadata_updated"
  | "workspace_closed"
  | "workspace_renamed"
  | "workspace_moved"
  | "workspace_reordered"
  | "workspace_focused"
  | "worktree_created"
  | "worktree_opened"
  | "worktree_removed"
  | "tab_created"
  | "tab_closed"
  | "tab_focused"
  | "tab_renamed"
  | "tab_moved"
  | "pane_created"
  | "pane_closed"
  | "pane_updated"
  | "pane_focused"
  | "pane_moved"
  | "pane_output_changed"
  | "pane_exited"
  | "pane_agent_detected"
  | "pane_agent_status_changed"
  | "layout_updated";

export interface HerdrErrorBody {
  error: {
    code: string;
    message: string;
    data?: unknown;
  };
}
