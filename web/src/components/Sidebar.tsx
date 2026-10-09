import type { SessionSummary } from "../api";

type Props = {
  sessions: SessionSummary[] | null;
  failed: boolean;
  currentId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRetry: () => void;
};

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function ago(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function Sidebar({ sessions, failed, currentId, onNew, onSelect, onRetry }: Props) {
  return (
    <nav className="sidebar" aria-label="Chats">
      <button type="button" className="primary new-chat" onClick={onNew}>
        + New chat
      </button>
      {failed ? (
        <div className="sidebar-note" role="alert">
          <p>Couldn't load chats.</p>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : sessions === null ? (
        <ul className="session-list" aria-busy="true" aria-label="Loading chats">
          {[0, 1, 2].map((i) => (
            <li key={i} className="skeleton" />
          ))}
        </ul>
      ) : sessions.length === 0 ? (
        <p className="sidebar-note">No chats yet</p>
      ) : (
        <ul className="session-list">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className="session"
                aria-current={s.id === currentId ? "true" : undefined}
                onClick={() => onSelect(s.id)}
              >
                <span className="session-title">{s.title}</span>
                <span className="muted session-time">{ago(s.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
