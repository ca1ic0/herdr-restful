import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { PaneInfo, PaneReadResult } from "../types/herdr";

function linesOf(result: PaneReadResult | null): string {
  if (!result) return "";
  if (Array.isArray(result.lines)) return result.lines.join("\n");
  if (typeof result.text === "string") return result.text;
  return JSON.stringify(result, null, 2);
}

export function PaneDetail({
  pane,
  onRefresh,
}: {
  pane: PaneInfo | null;
  onRefresh: () => void;
}) {
  const [output, setOutput] = useState<string>("");
  const [source, setSource] = useState("recent");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!pane) return;
    try {
      const res = await api.panes.output(pane.pane_id, source, 80);
      setOutput(linesOf(res));
      setNotice(null);
    } catch (err) {
      setNotice(err instanceof ApiError ? `${err.code}: ${err.message}` : String(err));
    }
  }, [pane, source]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!pane) {
    return <div className="detail empty">select a pane</div>;
  }

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await load();
      onRefresh();
      setNotice(null);
    } catch (err) {
      setNotice(err instanceof ApiError ? `${err.code}: ${err.message}` : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="detail">
      <div className="row">
        <strong>{pane.pane_id}</strong>
        <span className="meta">{pane.agent_status}</span>
        <span className="spacer" style={{ flex: 1 }} />
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="visible">visible</option>
          <option value="recent">recent</option>
          <option value="recent-unwrapped">recent-unwrapped</option>
          <option value="detection">detection</option>
        </select>
        <button onClick={() => void load()}>reload</button>
        <button onClick={() => void run(() => api.panes.focus(pane.pane_id))} disabled={busy}>
          focus
        </button>
        <button onClick={() => void run(() => api.panes.zoom(pane.pane_id, "toggle"))} disabled={busy}>
          zoom
        </button>
        <button
          onClick={() =>
            void run(() => api.panes.split({ pane_id: pane.pane_id, direction: "right", ratio: 0.5 }))
          }
          disabled={busy}
        >
          split
        </button>
        <button
          onClick={() => {
            if (confirm(`close pane ${pane.pane_id}?`)) {
              void run(() => api.panes.close(pane.pane_id));
            }
          }}
          disabled={busy}
        >
          close
        </button>
      </div>

      <div className="row">
        <input
          style={{ flex: 1 }}
          value={input}
          placeholder="send input to pane…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input) {
              void run(() => api.panes.sendText(pane.pane_id, input, true));
              setInput("");
            }
          }}
        />
        <button
          disabled={busy || !input}
          onClick={() => {
            void run(() => api.panes.sendText(pane.pane_id, input, true));
            setInput("");
          }}
        >
          send
        </button>
        <button
          disabled={busy}
          onClick={() => void run(() => api.panes.sendKeys(pane.pane_id, ["ctrl+c"]))}
        >
          ctrl+c
        </button>
      </div>

      {notice && <div className="error-banner">{notice}</div>}
      <pre>{output || "(no output)"}</pre>
    </div>
  );
}
