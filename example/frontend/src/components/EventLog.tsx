import type { LogEntry } from "../store/session";

function fmt(at: number): string {
  return new Date(at).toLocaleTimeString();
}

export function EventLog({ logs }: { logs: LogEntry[] }) {
  return (
    <div>
      <div className="section-title">events</div>
      {logs.length === 0 && <div className="empty">waiting for events…</div>}
      {logs.map((entry) => (
        <div key={entry.id} className="log-line">
          <span>{fmt(entry.at)}</span>
          <span className="evt">{entry.event}</span>
          <span>{entry.summary}</span>
        </div>
      ))}
    </div>
  );
}
