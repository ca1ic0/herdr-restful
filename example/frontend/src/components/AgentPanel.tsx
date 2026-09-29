import type { AgentInfo } from "../types/herdr";
import { StatusDot } from "./WorkspaceSidebar";

function agentLabel(agent: AgentInfo): string {
  return agent.display_agent || agent.name || agent.agent || agent.pane_id;
}

export function AgentPanel({
  agents,
  selectedPaneId,
  onSelect,
}: {
  agents: AgentInfo[];
  selectedPaneId: string | null;
  onSelect: (paneId: string) => void;
}) {
  const sorted = [...agents].sort(
    (a, b) => (b.state_change_seq ?? 0) - (a.state_change_seq ?? 0),
  );

  return (
    <div>
      <div className="section-title">agents</div>
      {sorted.length === 0 && <div className="empty">no agents detected</div>}
      {sorted.map((agent) => (
        <div
          key={agent.pane_id}
          className={`agent-item ${agent.pane_id === selectedPaneId ? "active" : ""}`}
          onClick={() => onSelect(agent.pane_id)}
        >
          <StatusDot status={agent.agent_status} />
          <div style={{ flex: 1, overflow: "hidden" }}>
            <div className="label">{agentLabel(agent)}</div>
            <div className="meta">
              {agent.pane_id} · {agent.agent_status}
              {agent.state_change_seq ? ` · seq ${agent.state_change_seq}` : ""}
            </div>
            {agent.state_labels && Object.keys(agent.state_labels).length > 0 && (
              <div className="meta">
                {Object.entries(agent.state_labels)
                  .map(([k, v]) => `${k}=${v}`)
                  .join("  ")}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
