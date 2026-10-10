import { useState } from "react";
import type { ArtifactRef, Citation, ErrorBody } from "../api";
import { renderAnswer } from "../render";
import { AlertIcon, CheckIcon, CopyIcon, InfoIcon, PageIcon, PenIcon, PlayIcon } from "./icons";

export type UiMessage = {
  key: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  route: string | null;
  status: "streaming" | "complete" | "error";
  stage?: "retrieving" | "generating";
  error?: ErrorBody | null;
  artifact?: ArtifactRef | null;
  request?: { content: string; hint: "essay" | "artifact" | null };
};

type Props = {
  message: UiMessage;
  cloudAvailable: boolean;
  onOpenArtifact: (ref: ArtifactRef) => void;
  onRetry: (m: UiMessage) => void;
  onSwitchToCloud: (m: UiMessage) => void;
};

const STAGE_TEXT = { retrieving: "Searching transcripts…", generating: "Writing…" };

function isRefusal(m: UiMessage): boolean {
  return m.status === "complete" && m.route !== "chat" && m.citations.length === 0 && !m.artifact;
}

/** Error text with `commands` shown as copyable code. */
function ErrorText({ text }: { text: string }) {
  return (
    <p>
      {text.split(/(`[^`]+`)/).map((part, i) =>
        part.startsWith("`") ? (
          <code key={i} className="command">
            {part.slice(1, -1)}
            <button type="button" className="copy-inline" onClick={() => navigator.clipboard.writeText(part.slice(1, -1))}>
              Copy
            </button>
          </code>
        ) : (
          part
        ),
      )}
    </p>
  );
}

function errorText(error: ErrorBody | null | undefined): string {
  if (!error) return "This answer didn't complete.";
  if (error.code === "provider_timeout") return "The model took too long.";
  return error.message;
}

type SourceGroup = { key: string; guest: string; title: string; items: { n: number; c: Citation }[] };

/** One row per episode: the same episode often supplies several passages, shown as timestamp links. */
function groupSources(citations: Citation[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  citations.forEach((c, i) => {
    const key = c.slug ?? c.title;
    const group = groups.get(key) ?? { key, guest: guestName(c.guest), title: c.title.split(" | ")[0], items: [] };
    group.items.push({ n: i + 1, c });
    groups.set(key, group);
  });
  return [...groups.values()];
}

/** "00:01:14" -> "1:14", "01:15:30" -> "1:15:30", like YouTube. */
function shortTs(ts: string | null): string {
  if (!ts) return "";
  const [h, m, s] = ts.split(":").map(Number);
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return `${h ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

/** Repeat guests are numbered in the dataset ("Elena Verna 4.0"); the episode title already tells them apart. */
const guestName = (guest: string | null) => (guest ?? "Unknown guest").replace(/\s+\d+\.0$/, "");

function Sources({ citations }: { citations: Citation[] }) {
  return (
    <section className="sources" aria-label="Sources">
      <h3 className="sources-label">Sources</h3>
      <ol className="source-list">
        {groupSources(citations).map((g) => (
          <li key={g.key} className="source">
            <span className="source-title" title={`${g.guest} — ${g.title}`}>
              <strong>{g.guest}</strong> <span className="muted">{g.title}</span>
            </span>
            <span className="source-links">
              {g.items.map(({ n, c }) => {
                const label = `Source ${n}: ${g.guest}, ${g.title}${c.ts ? ` at ${shortTs(c.ts)}` : ""}`;
                const text = (
                  <>
                    <span className="source-n">{n}</span>
                    {c.ts ? shortTs(c.ts) : "link"}
                  </>
                );
                return c.url ? (
                  <a key={n} className="source-link" href={c.url} target="_blank" rel="noopener noreferrer" aria-label={label}>
                    <PlayIcon size={11} />
                    {text}
                  </a>
                ) : (
                  <span key={n} className="source-link" aria-label={label}>
                    {text}
                  </span>
                );
              })}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function CopyAnswer({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button type="button" className="ghost-button" onClick={copy} aria-label="Copy answer">
      {copied ? <CheckIcon /> : <CopyIcon />} {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function MessageView({ message: m, cloudAvailable, onOpenArtifact, onRetry, onSwitchToCloud }: Props) {
  if (m.role === "user") {
    return <div className="msg user">{m.content}</div>;
  }
  const canRetry = Boolean(m.request);
  return (
    <div className="msg assistant">
      {m.status === "streaming" && m.stage && (
        <p className="status-line">
          <span className="spinner" aria-hidden="true" /> {STAGE_TEXT[m.stage]}
        </p>
      )}
      {isRefusal(m) ? (
        <div className="callout" role="note">
          <InfoIcon /> <span>{m.content}</span>
        </div>
      ) : (
        m.content && <div className="answer" dangerouslySetInnerHTML={{ __html: renderAnswer(m.content, m.citations) }} />
      )}
      {m.status === "error" && (
        <div className="error-card" role="alert">
          <strong>
            <AlertIcon /> Something went wrong
          </strong>
          <ErrorText text={errorText(m.error)} />
          {canRetry && (
            <div className="actions">
              <button type="button" onClick={() => onRetry(m)}>
                Retry
              </button>
              {cloudAvailable && m.error?.code?.startsWith("provider_") && (
                <button type="button" onClick={() => onSwitchToCloud(m)}>
                  Switch to Cloud
                </button>
              )}
            </div>
          )}
        </div>
      )}
      {m.artifact && (
        <div className="artifact-card">
          <span className="artifact-icon">{m.route === "essay" ? <PenIcon size={18} /> : <PageIcon size={18} />}</span>
          <div className="artifact-meta">
            <strong>{m.artifact.title}</strong>
            <span className="muted small">{m.route === "essay" ? "Ship 30 essay" : m.artifact.type === "html" ? "One-pager · HTML" : "Document · Markdown"}</span>
          </div>
          <button type="button" onClick={() => onOpenArtifact(m.artifact!)}>
            Open
          </button>
        </div>
      )}
      {m.citations.length > 0 && <Sources citations={m.citations} />}
      {m.status === "complete" && m.content && !isRefusal(m) && (
        <div className="msg-actions">
          <CopyAnswer text={m.content} />
        </div>
      )}
    </div>
  );
}
