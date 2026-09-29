import type { AgentStatus, WorkspaceInfo } from "../types/herdr";

export function StatusDot({ status, online }: { status?: AgentStatus; online?: boolean }) {
  const cls = online === true ? "online" : online === false ? "offline" : (status ?? "unknown");
  return <span className={`dot ${cls}`} />;
}

export function StatusBadge({ status }: { status?: AgentStatus }) {
  return <span className={`badge ${status ?? "unknown"}`}>{status ?? "unknown"}</span>;
}

export function WorkspaceSidebar({
  workspaces,
  order,
  focusedId,
  onSelect,
}: {
  workspaces: Record<string, WorkspaceInfo>;
  order: string[];
  focusedId: string | null;
  onSelect: (id: string) => void;
}) {
  const items = order.map((id) => workspaces[id]).filter(Boolean);

  return (
    <div>
      <div className="section-title">workspaces</div>
      {items.length === 0 && <div className="empty">no workspaces</div>}
      {items.map((ws) => (
        <div
          key={ws.workspace_id}
          className={`ws-item ${ws.workspace_id === focusedId ? "active" : ""}`}
          onClick={() => onSelect(ws.workspace_id)}
        >
          <StatusDot status={ws.agent_status} />
          <span className="label">
            <span className="meta">{ws.number}</span> {ws.label}
          </span>
          <span className="meta">
            {ws.tab_count}t / {ws.pane_count}p
          </span>
        </div>
      ))}
    </div>
  );
}
