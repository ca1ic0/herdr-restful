import { useState } from "react";
import { api } from "../api/client";
import { StatusDot } from "./WorkspaceSidebar";

export function Toolbar({
  connected,
  version,
  workspaceId,
  onRefresh,
}: {
  connected: boolean;
  version: string | null;
  workspaceId: string | null;
  onRefresh: () => void;
}) {
  const [label, setLabel] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const wrap = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await onRefresh();
      setNotice(null);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="toolbar">
      <span className="title">herdr</span>
      <span className="pill">
        <StatusDot online={connected} /> {connected ? "live" : "reconnecting"}
      </span>
      {version && <span className="pill">herdr {version}</span>}
      <span className="spacer" />
      {notice && <span className="pill">{notice}</span>}
      <input
        placeholder="new workspace label"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        style={{ width: 180 }}
      />
      <button
        onClick={() =>
          void wrap(async () => {
            await api.workspaces.create({ label: label || undefined, focus: true });
            setLabel("");
          })
        }
      >
        + workspace
      </button>
      <button
        onClick={() =>
          void wrap(() => api.tabs.create({ workspace_id: workspaceId ?? undefined, focus: true }))
        }
      >
        + tab
      </button>
      <button onClick={() => void wrap(() => api.notifications.show("herdr dashboard", "ping"))}>
        notify
      </button>
      <button className="primary" onClick={() => void onRefresh()}>
        refresh
      </button>
    </div>
  );
}
