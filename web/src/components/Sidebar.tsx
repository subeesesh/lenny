import type { SessionSummary } from "../api";
import { PlusIcon, TrashIcon } from "./icons";

type Props = {
  sessions: SessionSummary[] | null;
  failed: boolean;
  currentId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (session: SessionSummary) => void;
  onRetry: () => void;
};

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const KINDS: [RegExp, string][] = [
  [/^\s*write (?:a )?ship ?30 essay (?:on|about) (.+)$/i, "Essay"],
  [/^\s*make (?:a |an )?(?:html )?one-pager (?:on|about) (.+)$/i, "One-pager"],
  [/^\s*make (?:a |an )?markdown doc(?:ument)? (?:on|about) (.+)$/i, "Doc"],
];

/** Chat titles come from the first message; show the topic and a small tag instead of the request phrasing. */
export function displayTitle(title: string): { text: string; kind: string | null } {
  for (const [pattern, kind] of KINDS) {
    const match = title.match(pattern);
    if (match) return { text: match[1], kind };
  }
  return { text: title, kind: null };
}

function ago(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function Sidebar({ sessions, failed, currentId, onNew, onSelect, onDelete, onRetry }: Props) {
  return (
    <nav className="sidebar" aria-label="Chats">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          L
        </span>
        <span className="brand-name">Lenny Growth Assistant</span>
      </div>
      <button type="button" className="new-chat" onClick={onNew}>
        <PlusIcon /> New chat
      </button>
      <h2 className="sidebar-label">Chats</h2>
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
          {sessions.map((s) => {
            const { text, kind } = displayTitle(s.title);
            return (
            <li key={s.id} className="session-row">
              <button
                type="button"
                className="session"
                aria-current={s.id === currentId ? "true" : undefined}
                onClick={() => onSelect(s.id)}
              >
                <span className="session-title">{text}</span>
                <span className="session-meta">
                  {kind && <span className="tag">{kind}</span>}
                  <span className="session-time">{ago(s.updated_at)}</span>
                </span>
              </button>
              <button
                type="button"
                className="session-delete"
                aria-label={`Delete chat: ${s.title}`}
                title="Delete chat"
                onClick={() => onDelete(s)}
              >
                <TrashIcon />
              </button>
            </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
