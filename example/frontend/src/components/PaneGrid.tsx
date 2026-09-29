import type { PaneInfo } from "../types/herdr";
import { StatusBadge, StatusDot } from "./WorkspaceSidebar";

function paneTitle(pane: PaneInfo): string {
  return pane.display_agent || pane.title || pane.label || pane.terminal_title_stripped || pane.pane_id;
}

export function PaneGrid({
  panes,
  selectedPaneId,
  focusedPaneId,
  onSelect,
}: {
  panes: PaneInfo[];
  selectedPaneId: string | null;
  focusedPaneId: string | null;
  onSelect: (id: string) => void;
}) {
  if (panes.length === 0) {
    return <div className="empty">no panes in this tab</div>;
  }

  return (
    <div className="pane-grid">
      {panes.map((pane) => (
        <div
          key={pane.pane_id}
          className={[
            "pane-tile",
            pane.pane_id === selectedPaneId ? "selected" : "",
            pane.pane_id === focusedPaneId ? "focused" : "",
          ].join(" ")}
          onClick={() => onSelect(pane.pane_id)}
        >
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="pane-title">
              <StatusDot status={pane.agent_status} /> {paneTitle(pane)}
            </div>
            <StatusBadge status={pane.agent_status} />
          </div>
          <div className="pane-sub">{pane.foreground_cwd || pane.cwd || "—"}</div>
          {pane.title && pane.title !== paneTitle(pane) && (
            <div className="pane-sub">{pane.title}</div>
          )}
          <div className="pane-sub">
            {pane.agent ? `${pane.agent} · ` : ""}
            {pane.pane_id} · rev {pane.revision}
          </div>
          {pane.state_labels && Object.keys(pane.state_labels).length > 0 && (
            <div className="pane-sub">
              {Object.entries(pane.state_labels).map(([k, v]) => (
                <span key={k} className="badge" style={{ marginRight: 4 }}>
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
          {pane.scroll && (
            <div className="pane-sub">
              scroll {pane.scroll.offset_from_bottom}/{pane.scroll.max_offset_from_bottom}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
