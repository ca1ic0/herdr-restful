import { useMemo } from "react";
import { api } from "./api/client";
import { useHerdrSession } from "./hooks/useHerdrSession";
import { AgentPanel } from "./components/AgentPanel";
import { EventLog } from "./components/EventLog";
import { PaneDetail } from "./components/PaneDetail";
import { PaneGrid } from "./components/PaneGrid";
import { TabBar } from "./components/TabBar";
import { Toolbar } from "./components/Toolbar";
import { WorkspaceSidebar } from "./components/WorkspaceSidebar";
import type { AgentInfo, PaneInfo, TabInfo } from "./types/herdr";

export default function App() {
  const { state, dispatch, refresh, logs, error } = useHerdrSession();

  const workspaceTabs = useMemo<TabInfo[]>(
    () =>
      Object.values(state.tabs)
        .filter((t) => t.workspace_id === state.focusedWorkspaceId)
        .sort((a, b) => a.number - b.number),
    [state.tabs, state.focusedWorkspaceId],
  );

  const activeTabId = state.focusedTabId && state.tabs[state.focusedTabId]?.workspace_id === state.focusedWorkspaceId
    ? state.focusedTabId
    : (workspaceTabs.find((t) => t.focused)?.tab_id ?? workspaceTabs[0]?.tab_id ?? null);

  const tabPanes = useMemo<PaneInfo[]>(
    () =>
      Object.values(state.panes)
        .filter((p) => p.tab_id === activeTabId)
        .sort((a, b) => a.pane_id.localeCompare(b.pane_id)),
    [state.panes, activeTabId],
  );

  const agents = useMemo<AgentInfo[]>(
    () =>
      Object.values(state.agents).filter(
        (a) => a.agent || a.display_agent || a.agent_status !== "unknown",
      ),
    [state.agents],
  );

  const selectedPane =
    (state.selectedPaneId && state.panes[state.selectedPaneId]) ||
    tabPanes[0] ||
    null;

  return (
    <div className="app">
      <Toolbar
        connected={state.connected}
        version={state.version}
        workspaceId={state.focusedWorkspaceId}
        onRefresh={refresh}
      />

      <div className="sidebar">
        <WorkspaceSidebar
          workspaces={state.workspaces}
          order={state.workspaceOrder}
          focusedId={state.focusedWorkspaceId}
          onSelect={(id) => dispatch({ type: "select-workspace", workspaceId: id })}
        />
      </div>

      <div className="main">
        {error && <div className="error-banner">{error}</div>}
        <TabBar
          tabs={workspaceTabs}
          focusedId={activeTabId}
          onSelect={(id) => dispatch({ type: "select-tab", tabId: id })}
          onClose={(id) => {
            void api.tabs.close(id).then(refresh);
          }}
        />
        <PaneGrid
          panes={tabPanes}
          selectedPaneId={selectedPane?.pane_id ?? null}
          focusedPaneId={state.focusedPaneId}
          onSelect={(id) => dispatch({ type: "select-pane", paneId: id })}
        />
        <PaneDetail pane={selectedPane} onRefresh={refresh} />
      </div>

      <div className="agents">
        <AgentPanel
          agents={agents}
          selectedPaneId={selectedPane?.pane_id ?? null}
          onSelect={(id) => dispatch({ type: "select-pane", paneId: id })}
        />
      </div>

      <div className="log">
        <EventLog logs={logs} />
      </div>
    </div>
  );
}
