/**
 * Render the dashboard against a mocked REST + SSE layer and assert that real
 * herdr data actually reaches the DOM.
 */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import type { SessionSnapshot } from "../src/types/herdr";

const snapshot: SessionSnapshot = {
  version: "0.9.0",
  protocol: 22,
  focused_workspace_id: "w1",
  focused_tab_id: "w1:t1",
  focused_pane_id: "w1:p1",
  workspaces: [
    {
      workspace_id: "w1",
      number: 1,
      label: "api-server",
      focused: true,
      pane_count: 2,
      tab_count: 1,
      active_tab_id: "w1:t1",
      agent_status: "working",
    },
    {
      workspace_id: "w2",
      number: 2,
      label: "docs",
      focused: false,
      pane_count: 1,
      tab_count: 1,
      active_tab_id: "w2:t1",
      agent_status: "idle",
    },
  ],
  tabs: [
    {
      tab_id: "w1:t1",
      workspace_id: "w1",
      number: 1,
      label: "main",
      focused: true,
      pane_count: 2,
      agent_status: "working",
    },
    {
      tab_id: "w2:t1",
      workspace_id: "w2",
      number: 1,
      label: "notes",
      focused: false,
      pane_count: 1,
      agent_status: "idle",
    },
  ],
  panes: [
    {
      pane_id: "w1:p1",
      terminal_id: "term_a",
      workspace_id: "w1",
      tab_id: "w1:t1",
      focused: true,
      agent_status: "working",
      revision: 12,
      agent: "claude",
      display_agent: "Claude: auth",
      cwd: "/repo",
      title: "refactor auth",
    },
    {
      pane_id: "w1:p2",
      terminal_id: "term_b",
      workspace_id: "w1",
      tab_id: "w1:t1",
      focused: false,
      agent_status: "idle",
      revision: 3,
      cwd: "/repo/tests",
      terminal_title_stripped: "pytest",
    },
    {
      pane_id: "w2:p1",
      terminal_id: "term_c",
      workspace_id: "w2",
      tab_id: "w2:t1",
      focused: false,
      agent_status: "blocked",
      revision: 8,
      agent: "codex",
      display_agent: "Codex",
      cwd: "/docs",
    },
  ],
  layouts: [],
  agents: [],
};

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  listeners = new Map<string, EventListener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
    queueMicrotask(() => this.onopen?.());
  }

  addEventListener(name: string, fn: EventListener) {
    const list = this.listeners.get(name) ?? [];
    list.push(fn);
    this.listeners.set(name, list);
  }

  close() {}

  emit(name: string, data: unknown) {
    const ev = { data: JSON.stringify(data) } as MessageEvent<string>;
    for (const fn of this.listeners.get(name) ?? []) fn(ev);
  }
}

function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const ok = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    if (url.includes("/session/snapshot")) return ok({ type: "session_snapshot", snapshot });
    if (url.includes("/panes/") && url.includes("/output"))
      return ok({ type: "pane_read", lines: ["$ npm test", "ok 4 passed", "$ "] });
    if (url.includes("/workspaces")) return ok({ type: "workspace_list", workspaces: snapshot.workspaces });
    return ok({});
  });
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", mockFetch());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App dashboard", () => {
  it("renders workspaces from the snapshot", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/api-server/)).toBeTruthy());
    expect(screen.getByText(/docs/)).toBeTruthy();
  });

  it("renders panes of the focused tab with agent status", async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getAllByText(/Claude: auth/).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/refactor auth/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/pytest/).length).toBeGreaterThan(0);

    // w2:p1 lives in another tab, so it must not appear in the pane grid
    await waitFor(() => expect(container.querySelector(".pane-grid")).toBeTruthy());
    expect(container.querySelector(".pane-grid")!.textContent).not.toMatch(/Codex/);
  });

  it("shows the pane detail with terminal output", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/ok 4 passed/)).toBeTruthy());
  });

  it("lists the agents that have an identity", async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getAllByText(/Claude: auth/).length).toBeGreaterThan(0));
    // the agent panel is global: it also lists the agent in another tab
    const panel = container.querySelector(".agents")!;
    await waitFor(() => expect(panel.textContent).toMatch(/Codex/));
    expect(panel.textContent).toMatch(/w1:p1/);
  });

  it("opens an SSE stream to the bridge", async () => {
    render(<App />);
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
    expect(FakeEventSource.instances[0].url).toBe("/api/v1/events");
  });

  it("updates the DOM from live SSE events", async () => {
    render(<App />);
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.getByText(/api-server/)).toBeTruthy());

    const source = FakeEventSource.instances[0];
    act(() => {
      source.emit("workspace_renamed", {
        event: "workspace_renamed",
        data: { type: "workspace_renamed", workspace_id: "w1", label: "renamed-live" },
      });
    });

    await waitFor(() => expect(screen.getAllByText(/renamed-live/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/api-server/)).toBeNull();
  });

  it("reacts to pane_agent_status_changed", async () => {
    render(<App />);
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));

    const source = FakeEventSource.instances[0];
    act(() => {
      source.emit("pane_agent_status_changed", {
        event: "pane_agent_status_changed",
        data: {
          type: "pane_agent_status_changed",
          pane_id: "w1:p1",
          workspace_id: "w1",
          agent_status: "blocked",
          display_agent: "Claude: auth",
        },
      });
    });

    await waitFor(() => expect(screen.getAllByText("blocked").length).toBeGreaterThan(0));
  });
});
