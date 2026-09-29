/**
 * Session store: a snapshot-seeded state updated by herdr SSE events.
 *
 * The reducer consumes the herdr event envelope (`{event, data}`) and keeps
 * workspace / tab / pane / layout / agent maps in sync.
 */

import type {
  AgentInfo,
  HerdrEventEnvelope,
  PaneInfo,
  PaneLayoutSnapshot,
  SessionSnapshot,
  TabInfo,
  WorkspaceInfo,
} from "../types/herdr";

export interface SessionState {
  connected: boolean;
  lastEventAt: number | null;
  version: string | null;
  protocol: number | null;
  focusedWorkspaceId: string | null;
  focusedTabId: string | null;
  focusedPaneId: string | null;
  workspaces: Record<string, WorkspaceInfo>;
  workspaceOrder: string[];
  tabs: Record<string, TabInfo>;
  panes: Record<string, PaneInfo>;
  layouts: Record<string, PaneLayoutSnapshot>;
  agents: Record<string, AgentInfo>;
  selectedPaneId: string | null;
  eventLog: LogEntry[];
}

export interface LogEntry {
  id: number;
  at: number;
  event: string;
  summary: string;
}

export const initialState: SessionState = {
  connected: false,
  lastEventAt: null,
  version: null,
  protocol: null,
  focusedWorkspaceId: null,
  focusedTabId: null,
  focusedPaneId: null,
  workspaces: {},
  workspaceOrder: [],
  tabs: {},
  panes: {},
  layouts: {},
  agents: {},
  selectedPaneId: null,
  eventLog: [],
};

const MAX_LOG = 200;
let logSeq = 0;

function log(state: SessionState, event: string, summary: string): LogEntry[] {
  const entry: LogEntry = { id: ++logSeq, at: Date.now(), event, summary };
  return [entry, ...state.eventLog].slice(0, MAX_LOG);
}

function upsertAgents(agents: Record<string, AgentInfo>, pane: PaneInfo): Record<string, AgentInfo> {
  if (!pane.agent && !pane.display_agent) return agents;
  const next = { ...agents };
  next[pane.pane_id] = {
    ...(next[pane.pane_id] ?? { pane_id: pane.pane_id }),
    ...next[pane.pane_id],
    ...pane,
    pane_id: pane.pane_id,
  } as AgentInfo;
  return next;
}

export function applySnapshot(state: SessionState, snapshot: SessionSnapshot): SessionState {
  const workspaces: Record<string, WorkspaceInfo> = {};
  const workspaceOrder: string[] = [];
  for (const ws of snapshot.workspaces ?? []) {
    workspaces[ws.workspace_id] = ws;
    workspaceOrder.push(ws.workspace_id);
  }

  const tabs: Record<string, TabInfo> = {};
  for (const tab of snapshot.tabs ?? []) tabs[tab.tab_id] = tab;

  const panes: Record<string, PaneInfo> = {};
  for (const pane of snapshot.panes ?? []) panes[pane.pane_id] = pane;

  const layouts: Record<string, PaneLayoutSnapshot> = {};
  for (const layout of snapshot.layouts ?? []) {
    layouts[layout.tab_id] = layout;
  }

  let agents: Record<string, AgentInfo> = {};
  for (const agent of snapshot.agents ?? []) agents[agent.pane_id] = agent;
  for (const pane of Object.values(panes)) agents = upsertAgents(agents, pane);

  return {
    ...state,
    version: snapshot.version,
    protocol: snapshot.protocol,
    focusedWorkspaceId: snapshot.focused_workspace_id ?? null,
    focusedTabId: snapshot.focused_tab_id ?? null,
    focusedPaneId: snapshot.focused_pane_id ?? null,
    selectedPaneId: state.selectedPaneId ?? snapshot.focused_pane_id ?? null,
    workspaces,
    workspaceOrder,
    tabs,
    panes,
    layouts,
    agents,
  };
}

export function reducer(state: SessionState, event: HerdrEventEnvelope): SessionState {
  const data = event.data ?? ({} as HerdrEventEnvelope["data"]);
  const kind = event.event;

  switch (kind) {
    case "workspace_created":
    case "workspace_updated":
    case "workspace_metadata_updated": {
      const ws = data.workspace as WorkspaceInfo;
      if (!ws) return state;
      const exists = ws.workspace_id in state.workspaces;
      return {
        ...state,
        workspaces: { ...state.workspaces, [ws.workspace_id]: ws },
        workspaceOrder: exists
          ? state.workspaceOrder
          : [...state.workspaceOrder, ws.workspace_id],
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `workspace ${ws.label}`),
      };
    }

    case "workspace_renamed": {
      const id = data.workspace_id as string;
      const label = data.label as string;
      const ws = state.workspaces[id];
      return {
        ...state,
        workspaces: ws ? { ...state.workspaces, [id]: { ...ws, label } } : state.workspaces,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `${id} -> ${label}`),
      };
    }

    case "workspace_moved":
    case "workspace_reordered": {
      const order = (data.workspaces as WorkspaceInfo[] | undefined) ?? [];
      return {
        ...state,
        workspaceOrder: order.map((w) => w.workspace_id),
        workspaces: order.reduce(
          (acc, w) => {
            acc[w.workspace_id] = w;
            return acc;
          },
          { ...state.workspaces },
        ),
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `order updated (${order.length})`),
      };
    }

    case "workspace_closed": {
      const id = data.workspace_id as string;
      const workspaces = { ...state.workspaces };
      delete workspaces[id];
      const tabs = { ...state.tabs };
      const panes = { ...state.panes };
      for (const [tid, tab] of Object.entries(tabs)) {
        if (tab.workspace_id === id) delete tabs[tid];
      }
      for (const [pid, pane] of Object.entries(panes)) {
        if (pane.workspace_id === id) delete panes[pid];
      }
      return {
        ...state,
        workspaces,
        tabs,
        panes,
        workspaceOrder: state.workspaceOrder.filter((w) => w !== id),
        focusedWorkspaceId: state.focusedWorkspaceId === id ? null : state.focusedWorkspaceId,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "workspace_focused": {
      const id = data.workspace_id as string;
      return {
        ...state,
        focusedWorkspaceId: id,
        workspaces: Object.fromEntries(
          Object.entries(state.workspaces).map(([k, w]) => [k, { ...w, focused: k === id }]),
        ),
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "tab_created": {
      const tab = data.tab as TabInfo;
      if (!tab) return state;
      return {
        ...state,
        tabs: { ...state.tabs, [tab.tab_id]: tab },
        lastEventAt: Date.now(),
        eventLog: log(state, kind, tab.tab_id),
      };
    }

    case "tab_closed": {
      const id = data.tab_id as string;
      const tabs = { ...state.tabs };
      delete tabs[id];
      const panes = { ...state.panes };
      for (const [pid, pane] of Object.entries(panes)) {
        if (pane.tab_id === id) delete panes[pid];
      }
      return {
        ...state,
        tabs,
        panes,
        focusedTabId: state.focusedTabId === id ? null : state.focusedTabId,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "tab_renamed": {
      const id = data.tab_id as string;
      const label = data.label as string;
      const tab = state.tabs[id];
      return {
        ...state,
        tabs: tab ? { ...state.tabs, [id]: { ...tab, label } } : state.tabs,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `${id} -> ${label}`),
      };
    }

    case "tab_moved": {
      const tabs = (data.tabs as TabInfo[] | undefined) ?? [];
      return {
        ...state,
        tabs: tabs.reduce(
          (acc, t) => {
            acc[t.tab_id] = t;
            return acc;
          },
          { ...state.tabs },
        ),
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `${data.tab_id}`),
      };
    }

    case "tab_focused": {
      const id = data.tab_id as string;
      return {
        ...state,
        focusedTabId: id,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "pane_created":
    case "pane_updated":
    case "pane_moved": {
      const pane = data.pane as PaneInfo;
      if (!pane) return state;
      return {
        ...state,
        panes: { ...state.panes, [pane.pane_id]: pane },
        agents: upsertAgents(state.agents, pane),
        lastEventAt: Date.now(),
        eventLog: log(state, kind, pane.pane_id),
      };
    }

    case "pane_closed": {
      const id = data.pane_id as string;
      const panes = { ...state.panes };
      delete panes[id];
      const agents = { ...state.agents };
      delete agents[id];
      return {
        ...state,
        panes,
        agents,
        focusedPaneId: state.focusedPaneId === id ? null : state.focusedPaneId,
        selectedPaneId: state.selectedPaneId === id ? null : state.selectedPaneId,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "pane_focused": {
      const id = data.pane_id as string;
      return {
        ...state,
        focusedPaneId: id,
        panes: Object.fromEntries(
          Object.entries(state.panes).map(([k, p]) => [k, { ...p, focused: k === id }]),
        ),
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "pane_exited": {
      const id = data.pane_id as string;
      return {
        ...state,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, id),
      };
    }

    case "pane_agent_detected":
    case "pane_agent_status_changed": {
      const id = data.pane_id as string;
      const pane = state.panes[id];
      const status = data.agent_status as PaneInfo["agent_status"] | undefined;
      const agent = data.agent as string | undefined;
      const displayAgent = data.display_agent as string | undefined;
      const title = data.title as string | undefined;
      const stateLabels = data.state_labels as Record<string, string> | undefined;

      const nextPane: PaneInfo | undefined = pane
        ? {
            ...pane,
            agent_status: status ?? pane.agent_status,
            agent: agent ?? pane.agent,
            display_agent: displayAgent ?? pane.display_agent,
            title: title ?? pane.title,
            state_labels: stateLabels ?? pane.state_labels,
          }
        : undefined;

      const agents = { ...state.agents };
      agents[id] = {
        ...(agents[id] ?? { pane_id: id, terminal_id: "" }),
        ...agents[id],
        pane_id: id,
        agent_status: (status ?? agents[id]?.agent_status ?? "unknown") as AgentInfo["agent_status"],
        agent: agent ?? agents[id]?.agent,
        display_agent: displayAgent ?? agents[id]?.display_agent,
        title: title ?? agents[id]?.title,
        state_labels: stateLabels ?? agents[id]?.state_labels,
        workspace_id: data.workspace_id as string,
      } as AgentInfo;

      return {
        ...state,
        panes: nextPane ? { ...state.panes, [id]: nextPane } : state.panes,
        agents,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, `${id} ${status ?? ""}`.trim()),
      };
    }

    case "layout_updated": {
      const layout = data.layout as PaneLayoutSnapshot;
      if (!layout) return state;
      return {
        ...state,
        layouts: { ...state.layouts, [layout.tab_id]: layout },
        lastEventAt: Date.now(),
        eventLog: log(state, kind, layout.tab_id),
      };
    }

    case "worktree_created":
    case "worktree_opened":
    case "worktree_removed": {
      return {
        ...state,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, String(data.workspace_id ?? "")),
      };
    }

    default:
      return {
        ...state,
        lastEventAt: Date.now(),
        eventLog: log(state, kind, ""),
      };
  }
}

export function selectWorkspace(state: SessionState, id: string | null): SessionState {
  return { ...state, focusedWorkspaceId: id };
}

export function selectPane(state: SessionState, id: string | null): SessionState {
  return { ...state, selectedPaneId: id };
}

export function setConnection(state: SessionState, connected: boolean): SessionState {
  return {
    ...state,
    connected,
    eventLog: log(state, connected ? "bridge.connected" : "bridge.disconnected", ""),
  };
}
