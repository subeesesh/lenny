import type { ArtifactRef, Citation, ErrorBody } from "../api";
import { renderAnswer } from "../render";

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

function Chips({ citations }: { citations: Citation[] }) {
  return (
    <ol className="chips" aria-label="Sources">
      {citations.map((c, i) => {
        const text = `[${i + 1}] ${c.guest ?? "Unknown guest"} — ${c.title}`;
        const label = `Source ${i + 1}: ${c.guest ?? "Unknown guest"}, ${c.title}`;
        return (
          <li key={c.chunk_id}>
            {c.url ? (
              <a className="chip" href={c.url} target="_blank" rel="noopener noreferrer" aria-label={label} title={text}>
                {text}
              </a>
            ) : (
              <span className="chip" aria-label={label} title={text}>
                {text}
              </span>
            )}
          </li>
        );
      })}
    </ol>
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
          <span aria-hidden="true">ⓘ</span> {m.content}
        </div>
      ) : (
        m.content && <div className="answer" dangerouslySetInnerHTML={{ __html: renderAnswer(m.content, m.citations) }} />
      )}
      {m.status === "error" && (
        <div className="error-card" role="alert">
          <strong>
            <span aria-hidden="true">⚠</span> Something went wrong
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
          <div>
            <strong>{m.artifact.title}</strong>
            <span className="muted"> · {m.artifact.type === "html" ? "HTML" : "Markdown"}</span>
          </div>
          <button type="button" onClick={() => onOpenArtifact(m.artifact!)}>
            Open
          </button>
        </div>
      )}
      {m.citations.length > 0 && <Chips citations={m.citations} />}
    </div>
  );
}
