import type {
  AgentListResult,
  AgentStatus,
  HerdrErrorBody,
  PaneListResult,
  PaneReadResult,
  SessionSnapshotResult,
  SplitDirection,
  TabListResult,
  WorkspaceListResult,
} from "../types/herdr";

const BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};

  if (!res.ok) {
    const err = body as Partial<HerdrErrorBody>;
    const code = err.error?.code ?? `http_${res.status}`;
    const message = err.error?.message ?? res.statusText;
    throw new ApiError(res.status, code, message);
  }
  return body as T;
}

export interface SplitPaneOptions {
  pane_id?: string;
  direction: SplitDirection;
  ratio?: number;
  cwd?: string;
  command?: string[];
  env?: Record<string, string>;
  label?: string;
}

export const api = {
  health: () => request<{ status: string; herdr: unknown }>("/health"),

  serverInfo: () => request<Record<string, unknown>>("/server"),

  snapshot: () => request<SessionSnapshotResult>("/session/snapshot"),

  workspaces: {
    list: () => request<WorkspaceListResult>("/workspaces"),
    create: (body: { cwd?: string; label?: string; focus?: boolean }) =>
      request<Record<string, unknown>>("/workspaces", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    rename: (id: string, label: string) =>
      request<Record<string, unknown>>(`/workspaces/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ label }),
      }),
    close: (id: string, closeGroup?: boolean) =>
      request<Record<string, unknown>>(
        `/workspaces/${encodeURIComponent(id)}${closeGroup ? "?close_group=true" : ""}`,
        { method: "DELETE" },
      ),
    focus: (id: string) =>
      request<Record<string, unknown>>(`/workspaces/${encodeURIComponent(id)}/focus`, {
        method: "POST",
      }),
  },

  tabs: {
    list: (workspaceId?: string) =>
      request<TabListResult>(
        `/tabs${workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ""}`,
      ),
    create: (body: { workspace_id?: string; label?: string; focus?: boolean }) =>
      request<Record<string, unknown>>("/tabs", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    close: (id: string) =>
      request<Record<string, unknown>>(`/tabs/${encodeURIComponent(id)}`, { method: "DELETE" }),
    focus: (id: string) =>
      request<Record<string, unknown>>(`/tabs/${encodeURIComponent(id)}/focus`, {
        method: "POST",
      }),
  },

  panes: {
    list: (workspaceId?: string, tabId?: string) => {
      const q = new URLSearchParams();
      if (workspaceId) q.set("workspace_id", workspaceId);
      if (tabId) q.set("tab_id", tabId);
      const qs = q.toString();
      return request<PaneListResult>(`/panes${qs ? `?${qs}` : ""}`);
    },
    current: () => request<Record<string, unknown>>("/panes/current"),
    get: (id: string) => request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}`),
    output: (id: string, source = "recent", lines = 60) =>
      request<PaneReadResult>(
        `/panes/${encodeURIComponent(id)}/output?source=${source}&lines=${lines}`,
      ),
    split: (opts: SplitPaneOptions) =>
      request<Record<string, unknown>>("/panes/split", {
        method: "POST",
        body: JSON.stringify(opts),
      }),
    zoom: (id: string, mode: "toggle" | "on" | "off" = "toggle") =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/zoom`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      }),
    resize: (id: string, direction: string, amount: number) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/resize`, {
        method: "POST",
        body: JSON.stringify({ direction, amount }),
      }),
    focus: (id: string) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/focus`, {
        method: "POST",
      }),
    close: (id: string) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}`, { method: "DELETE" }),
    rename: (id: string, label: string) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ label }),
      }),
    sendText: (id: string, text: string, submit = false) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/input/text`, {
        method: "POST",
        body: JSON.stringify({ text, submit }),
      }),
    sendKeys: (id: string, keys: string[]) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/input/keys`, {
        method: "POST",
        body: JSON.stringify({ keys }),
      }),
    processInfo: (id: string) =>
      request<Record<string, unknown>>(`/panes/${encodeURIComponent(id)}/process-info`),
  },

  agents: {
    list: () => request<AgentListResult>("/agents"),
    get: (paneId: string) =>
      request<Record<string, unknown>>(`/agents/${encodeURIComponent(paneId)}`),
    explain: (paneId: string) =>
      request<Record<string, unknown>>(`/agents/${encodeURIComponent(paneId)}/explain`),
    prompt: (paneId: string, prompt: string) =>
      request<Record<string, unknown>>(`/agents/${encodeURIComponent(paneId)}/prompt`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      }),
    wait: (paneId: string, until: AgentStatus, timeoutMs?: number) =>
      request<Record<string, unknown>>(`/agents/${encodeURIComponent(paneId)}/wait`, {
        method: "POST",
        body: JSON.stringify({ until, timeout_ms: timeoutMs }),
      }),
  },

  layout: {
    export: (tabId?: string) =>
      request<Record<string, unknown>>(
        `/layout/export${tabId ? `?tab_id=${encodeURIComponent(tabId)}` : ""}`,
      ),
  },

  notifications: {
    show: (title: string, body?: string) =>
      request<Record<string, unknown>>("/notifications", {
        method: "POST",
        body: JSON.stringify({ title, body }),
      }),
  },
};
