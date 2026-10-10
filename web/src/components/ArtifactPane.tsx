import { useState } from "react";
import type { Artifact } from "../api";
import { artifactDocument } from "../render";
import { BackIcon, CheckIcon, CloseIcon, CopyIcon, LockIcon } from "./icons";

type Props = { artifact: Artifact | null; loadingTitle: string | null; error: string | null; onClose: () => void };

export function ArtifactPane({ artifact, loadingTitle, error, onClose }: Props) {
  const [view, setView] = useState<"preview" | "source">("preview");
  const [copied, setCopied] = useState(false);
  const title = artifact?.title ?? loadingTitle ?? "Document";

  async function copy() {
    if (!artifact) return;
    await navigator.clipboard.writeText(artifact.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <aside className="artifact-pane" aria-label={`Document: ${title}`}>
      <header className="pane-header">
        <button type="button" className="quiet back" onClick={onClose}>
          <BackIcon /> Back
        </button>
        <div className="pane-title">
          <h2>{title}</h2>
          {artifact && <span className="muted small">{artifact.type === "html" ? "HTML" : "Markdown"}</span>}
        </div>
        <div className="pane-actions">
          <div role="group" aria-label="View" className="toggle">
            <button type="button" aria-pressed={view === "preview"} onClick={() => setView("preview")}>
              Preview
            </button>
            <button type="button" aria-pressed={view === "source"} onClick={() => setView("source")}>
              Source
            </button>
          </div>
          <button type="button" onClick={copy} disabled={!artifact}>
            {copied ? <CheckIcon /> : <CopyIcon />} {copied ? "Copied" : "Copy"}
          </button>
          <button type="button" className="quiet close" aria-label="Close document" onClick={onClose}>
            <CloseIcon size={18} />
          </button>
        </div>
      </header>
      {error ? (
        <div className="error-card" role="alert">
          <p>{error}</p>
        </div>
      ) : !artifact ? (
        <p className="status-line">
          <span className="spinner" aria-hidden="true" /> Loading…
        </p>
      ) : view === "preview" ? (
        <iframe className="artifact-frame" title={`Preview of ${artifact.title} (sandboxed)`} sandbox="" srcDoc={artifactDocument(artifact)} />
      ) : (
        <pre className="artifact-source">{artifact.content}</pre>
      )}
      <p className="sandbox-note muted small">
        <LockIcon size={14} /> Sandboxed: scripts, forms, links and external content are blocked.
      </p>
    </aside>
  );
}
