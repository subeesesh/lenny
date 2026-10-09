import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, NetworkError, sendMessage, type Artifact, type ArtifactRef, type Config, type SessionDetail, type SessionSummary } from "./api";
import { ArtifactPane } from "./components/ArtifactPane";
import { Composer } from "./components/Composer";
import { MessageView, type UiMessage } from "./components/MessageView";
import { NameDialog } from "./components/NameDialog";
import { ProviderBadge } from "./components/ProviderBadge";
import { Sidebar } from "./components/Sidebar";

const NAME_KEY = "lga.displayName";
const EXAMPLES = [
  "How do the guests think about finding product-market fit?",
  "What does Elena Verna say about growth loops?",
  "How should a new PM spend their first 90 days?",
];

const readName = () => {
  try {
    return localStorage.getItem(NAME_KEY);
  } catch {
    return null;
  }
};

let keyCounter = 0;
const nextKey = () => `m${++keyCounter}`;

function toUiMessages(detail: SessionDetail): UiMessage[] {
  const byMessage = new Map(detail.artifacts.map((a) => [a.message_id, a]));
  return detail.messages.map((m) => ({
    key: `db${m.id}`,
    role: m.role,
    content: m.content,
    citations: m.citations,
    route: m.route,
    status: m.status,
    artifact: byMessage.get(m.id) ?? null,
  }));
}

export default function App() {
  const [displayName, setDisplayName] = useState<string | null>(readName);
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [sessionsFailed, setSessionsFailed] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [title, setTitle] = useState("New chat");
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [serverDown, setServerDown] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pane, setPane] = useState<{ ref: ArtifactRef; artifact: Artifact | null; error: string | null } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const handleFailure = useCallback((err: unknown) => {
    if (err instanceof NetworkError) setServerDown(true);
  }, []);

  const loadSessions = useCallback(async () => {
    setSessionsFailed(false);
    try {
      setSessions(await api.sessions());
      setServerDown(false);
    } catch (err) {
      setSessionsFailed(true);
      handleFailure(err);
    }
  }, [handleFailure]);

  const loadConfig = useCallback(async () => {
    try {
      setConfig(await api.config());
    } catch (err) {
      handleFailure(err);
    }
  }, [handleFailure]);

  const reconnect = useCallback(() => {
    loadSessions();
    loadConfig();
  }, [loadSessions, loadConfig]);

  useEffect(reconnect, [reconnect]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPane(null);
        setDrawerOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const openArtifact = useCallback(
    async (ref: ArtifactRef, forSession: string | null = sessionId) => {
      if (!forSession) return;
      setPane({ ref, artifact: null, error: null });
      try {
        const artifact = await api.artifact(ref.id, forSession);
        setPane((p) => (p?.ref.id === ref.id ? { ...p, artifact } : p));
      } catch (err) {
        handleFailure(err);
        setPane((p) => (p?.ref.id === ref.id ? { ...p, error: "Couldn't load this document." } : p));
      }
    },
    [sessionId, handleFailure],
  );

  function newChat() {
    setSessionId(null);
    setTitle("New chat");
    setMessages([]);
    setPane(null);
    setDrawerOpen(false);
  }

  async function selectSession(id: string) {
    setDrawerOpen(false);
    setPane(null);
    try {
      const detail = await api.session(id);
      setSessionId(id);
      setTitle(detail.title);
      setMessages(toUiMessages(detail));
    } catch (err) {
      handleFailure(err);
      setAnnouncement("Couldn't open that chat.");
    }
  }

  function patchLast(update: (m: UiMessage) => UiMessage) {
    setMessages((ms) => [...ms.slice(0, -1), update(ms[ms.length - 1])]);
  }

  async function send(content: string, hint: "essay" | "artifact" | null) {
    if (busy || !displayName) return;
    setBusy(true);
    setAnnouncement("");
    const request = { content, hint };
    setMessages((ms) => [
      ...ms,
      { key: nextKey(), role: "user", content, citations: [], route: null, status: "complete" },
      { key: nextKey(), role: "assistant", content: "", citations: [], route: hint ?? "qa", status: "streaming", stage: "retrieving", request },
    ]);
    let id = sessionId;
    let finished = false;
    try {
      if (!id) {
        id = (await api.createSession(displayName)).id;
        setSessionId(id);
      }
      const forSession = id;
      await sendMessage(id, content, hint, (e) => {
        switch (e.event) {
          case "status":
            patchLast((m) => ({ ...m, stage: e.data.stage }));
            break;
          case "citations":
            patchLast((m) => ({ ...m, citations: e.data }));
            break;
          case "token":
            patchLast((m) => ({ ...m, content: m.content + e.data.text, stage: undefined }));
            break;
          case "artifact":
            patchLast((m) => ({ ...m, artifact: e.data }));
            openArtifact(e.data, forSession);
            break;
          case "done":
            finished = true;
            patchLast((m) => ({ ...m, status: "complete", stage: undefined }));
            setAnnouncement("Answer complete");
            break;
          case "error":
            finished = true;
            patchLast((m) => ({ ...m, status: "error", stage: undefined, error: e.data }));
            setAnnouncement(`Error: ${e.data.message}`);
            break;
        }
      });
      if (!finished) throw new ApiError("internal_error", "The connection closed before the answer finished.");
    } catch (err) {
      handleFailure(err);
      const message = err instanceof Error ? err.message : "Something went wrong.";
      const code = err instanceof ApiError ? err.code : "internal_error";
      patchLast((m) => ({ ...m, status: "error", stage: undefined, error: { code, message, request_id: "" } }));
      setAnnouncement(`Error: ${message}`);
    } finally {
      setBusy(false);
      loadSessions();
      if (id) api.session(id).then((d) => setTitle(d.title)).catch(() => undefined);
    }
  }

  async function switchProvider(provider: string) {
    try {
      setConfig(await api.setProvider(provider));
    } catch (err) {
      handleFailure(err);
      setAnnouncement(err instanceof Error ? err.message : "Couldn't switch the model.");
    }
  }

  function retry(m: UiMessage) {
    if (m.request) send(m.request.content, m.request.hint);
  }

  async function switchToCloud(m: UiMessage) {
    await switchProvider("anthropic");
    retry(m);
  }

  const cloud = config?.providers.find((p) => p.name === "anthropic");
  const cloudAvailable = Boolean(cloud?.available && config?.active.provider !== "anthropic");

  return (
    <div className={`app${pane ? " with-pane" : ""}${drawerOpen ? " drawer-open" : ""}`}>
      {serverDown && (
        <div className="banner" role="alert">
          <span aria-hidden="true">⚠</span> Can't reach the server.
          <button type="button" onClick={reconnect}>
            Retry
          </button>
        </div>
      )}
      <Sidebar
        sessions={sessions}
        failed={sessionsFailed}
        currentId={sessionId}
        onNew={newChat}
        onSelect={selectSession}
        onRetry={loadSessions}
      />
      <div className="drawer-scrim" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      <main className="chat">
        <header className="chat-header">
          <button type="button" className="quiet menu-button" aria-label="Open chats" onClick={() => setDrawerOpen(true)}>
            ☰
          </button>
          <h1 className="chat-title">{title}</h1>
          <ProviderBadge config={config} disabled={busy} onSelect={switchProvider} />
        </header>
        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty">
              <p>Ask anything about Lenny's Podcast. Answers come only from the episode transcripts, with sources.</p>
              <ul>
                {EXAMPLES.map((q) => (
                  <li key={q}>
                    <button type="button" className="example" disabled={busy} onClick={() => send(q, null)}>
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            messages.map((m) => (
              <MessageView
                key={m.key}
                message={m}
                cloudAvailable={cloudAvailable}
                onOpenArtifact={(ref) => openArtifact(ref)}
                onRetry={retry}
                onSwitchToCloud={switchToCloud}
              />
            ))
          )}
          <div ref={endRef} />
        </div>
        <Composer disabled={busy} onSend={send} />
      </main>
      {pane && <ArtifactPane artifact={pane.artifact} loadingTitle={pane.ref.title} error={pane.error} onClose={() => setPane(null)} />}
      <div className="visually-hidden" aria-live="polite">
        {announcement}
      </div>
      {!displayName && (
        <NameDialog
          onSave={(name) => {
            try {
              localStorage.setItem(NAME_KEY, name);
            } catch {
              /* private mode: keep the name for this visit only */
            }
            setDisplayName(name);
          }}
        />
      )}
    </div>
  );
}
