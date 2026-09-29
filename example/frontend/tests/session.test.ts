import { describe, expect, it } from "vitest";
import {
  applySnapshot,
  initialState,
  reducer,
  type SessionState,
} from "../src/store/session";
import type { HerdrEventEnvelope, SessionSnapshot } from "../src/types/herdr";

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
      label: "alpha",
      focused: true,
      pane_count: 1,
      tab_count: 1,
      active_tab_id: "w1:t1",
      agent_status: "working",
    },
  ],
  tabs: [
    {
      tab_id: "w1:t1",
      workspace_id: "w1",
      number: 1,
      label: "main",
      focused: true,
      pane_count: 1,
      agent_status: "working",
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
      revision: 1,
      agent: "claude",
    },
  ],
  layouts: [],
  agents: [],
};

function evt(event: string, data: Record<string, unknown>): HerdrEventEnvelope {
  return { event: event as HerdrEventEnvelope["event"], data: { type: event, ...data } };
}

function seeded(): SessionState {
  return applySnapshot(initialState, snapshot);
}

describe("applySnapshot", () => {
  it("seeds workspaces, tabs, panes and focus", () => {
    const s = seeded();
    expect(s.workspaceOrder).toEqual(["w1"]);
    expect(s.workspaces["w1"].label).toBe("alpha");
    expect(s.tabs["w1:t1"].focused).toBe(true);
    expect(s.panes["w1:p1"].agent).toBe("claude");
    expect(s.focusedWorkspaceId).toBe("w1");
    expect(s.focusedPaneId).toBe("w1:p1");
  });

  it("derives agents from panes", () => {
    const s = seeded();
    expect(s.agents["w1:p1"].agent).toBe("claude");
  });
});

describe("reducer", () => {
  it("applies workspace_created and keeps order", () => {
    let s = seeded();
    s = reducer(
      s,
      evt("workspace_created", {
        workspace: {
          workspace_id: "w2",
          number: 2,
          label: "beta",
          focused: false,
          pane_count: 1,
          tab_count: 1,
          active_tab_id: "w2:t1",
          agent_status: "idle",
        },
      }),
    );
    expect(s.workspaceOrder).toEqual(["w1", "w2"]);
    expect(s.workspaces["w2"].label).toBe("beta");
  });

  it("applies workspace_renamed", () => {
    let s = seeded();
    s = reducer(s, evt("workspace_renamed", { workspace_id: "w1", label: "renamed" }));
    expect(s.workspaces["w1"].label).toBe("renamed");
  });

  it("drops tabs and panes when a workspace closes", () => {
    let s = seeded();
    s = reducer(s, evt("workspace_closed", { workspace_id: "w1" }));
    expect(s.workspaces["w1"]).toBeUndefined();
    expect(s.tabs["w1:t1"]).toBeUndefined();
    expect(s.panes["w1:p1"]).toBeUndefined();
    expect(s.workspaceOrder).toEqual([]);
  });

  it("updates focus on workspace_focused and pane_focused", () => {
    let s = seeded();
    s = reducer(s, evt("workspace_focused", { workspace_id: "w1" }));
    expect(s.focusedWorkspaceId).toBe("w1");
    s = reducer(s, evt("pane_focused", { pane_id: "w1:p1", workspace_id: "w1" }));
    expect(s.focusedPaneId).toBe("w1:p1");
  });

  it("upserts panes on pane_updated", () => {
    let s = seeded();
    s = reducer(
      s,
      evt("pane_updated", {
        pane: {
          pane_id: "w1:p1",
          terminal_id: "term_a",
          workspace_id: "w1",
          tab_id: "w1:t1",
          focused: true,
          agent_status: "blocked",
          revision: 2,
          agent: "claude",
          title: "waiting",
        },
      }),
    );
    expect(s.panes["w1:p1"].agent_status).toBe("blocked");
    expect(s.panes["w1:p1"].title).toBe("waiting");
    expect(s.agents["w1:p1"].agent_status).toBe("blocked");
  });

  it("applies pane_agent_status_changed even for unknown panes", () => {
    let s = seeded();
    s = reducer(
      s,
      evt("pane_agent_status_changed", {
        pane_id: "w1:p9",
        workspace_id: "w1",
        agent_status: "done",
        agent: "codex",
      }),
    );
    expect(s.agents["w1:p9"].agent_status).toBe("done");
    expect(s.agents["w1:p9"].agent).toBe("codex");
  });

  it("stores layout snapshots keyed by workspace:tab", () => {
    let s = seeded();
    s = reducer(
      s,
      evt("layout_updated", {
        layout: {
          workspace_id: "w1",
          tab_id: "w1:t1",
          zoomed: false,
          area: { x: 0, y: 0, width: 10, height: 10 },
          focused_pane_id: "w1:p1",
          panes: [],
          splits: [],
        },
      }),
    );
    expect(s.layouts["w1:t1"]).toBeDefined();
    expect(s.layouts["w1:t1"].tab_id).toBe("w1:t1");
  });

  it("removes panes on pane_closed and clears selection", () => {
    let s: SessionState = { ...seeded(), selectedPaneId: "w1:p1" };
    s = reducer(s, evt("pane_closed", { pane_id: "w1:p1", workspace_id: "w1" }));
    expect(s.panes["w1:p1"]).toBeUndefined();
    expect(s.selectedPaneId).toBeNull();
    expect(s.agents["w1:p1"]).toBeUndefined();
  });

  it("reorders workspaces on workspace_reordered", () => {
    let s = seeded();
    s = reducer(
      s,
      evt("workspace_created", {
        workspace: {
          workspace_id: "w2",
          number: 2,
          label: "beta",
          focused: false,
          pane_count: 1,
          tab_count: 1,
          active_tab_id: "w2:t1",
          agent_status: "idle",
        },
      }),
    );
    s = reducer(
      s,
      evt("workspace_reordered", {
        workspace_ids: ["w2", "w1"],
        workspaces: [
          { ...s.workspaces["w2"], number: 1 },
          { ...s.workspaces["w1"], number: 2 },
        ],
      }),
    );
    expect(s.workspaceOrder).toEqual(["w2", "w1"]);
  });

  it("keeps a bounded event log", () => {
    let s = seeded();
    for (let i = 0; i < 250; i += 1) {
      s = reducer(s, evt("pane_focused", { pane_id: "w1:p1", workspace_id: "w1" }));
    }
    expect(s.eventLog.length).toBeLessThanOrEqual(200);
  });
});
