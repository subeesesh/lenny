import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { api, ApiError, NetworkError, sendMessage, type Artifact, type ArtifactRef, type Config, type SessionDetail, type SessionSummary } from "./api";
import { ArtifactPane } from "./components/ArtifactPane";
import { Composer, type Prefill } from "./components/Composer";
import { MessageView, type UiMessage } from "./components/MessageView";
import { NameDialog } from "./components/NameDialog";
import { ProviderBadge } from "./components/ProviderBadge";
import { AlertIcon, ChatIcon, MenuIcon, PageIcon, PenIcon } from "./components/icons";
import { Sidebar, displayTitle } from "./components/Sidebar";
import { pickSuggestions } from "./suggestions";
import { SidebarResizer, readSidebarWidth } from "./components/SidebarResizer";

const NAME_KEY = "lga.displayName";

const TILES = [
  { icon: <ChatIcon size={20} />, title: "Ask a question", text: "A cited answer from ~290 episodes.", prefill: "" },
  { icon: <PenIcon size={20} />, title: "Write a Ship 30 essay", text: "A grounded essay with a sources list.", prefill: "Write a Ship 30 essay on " },
  { icon: <PageIcon size={20} />, title: "Make a one-pager", text: "A shareable page you can copy.", prefill: "Make a one-pager on " },
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
  const [sidebarWidth, setSidebarWidth] = useState(readSidebarWidth);
  const [prefill, setPrefill] = useState<Prefill | null>(null);
  const [suggestions, setSuggestions] = useState(() => pickSuggestions());
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
    setSuggestions(pickSuggestions());
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

  async function deleteSession(s: SessionSummary) {
    if (!window.confirm(`Delete "${s.title}"? This removes its messages and documents and can't be undone.`)) return;
    try {
      await api.deleteSession(s.id);
      if (s.id === sessionId) newChat();
      setAnnouncement("Chat deleted");
    } catch (err) {
      handleFailure(err);
      setAnnouncement("Couldn't delete that chat.");
    } finally {
      loadSessions();
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
    <div
      className={`app${pane ? " with-pane" : ""}${drawerOpen ? " drawer-open" : ""}`}
      style={{ "--sidebar": `${sidebarWidth}px` } as CSSProperties}
    >
      {serverDown && (
        <div className="banner" role="alert">
          <AlertIcon /> Can't reach the server.
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
        onDelete={deleteSession}
        onRetry={loadSessions}
      />
      <SidebarResizer width={sidebarWidth} onChange={setSidebarWidth} />
      <div className="drawer-scrim" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      <main className="chat">
        <header className="chat-header">
          <button type="button" className="quiet menu-button" aria-label="Open chats" onClick={() => setDrawerOpen(true)}>
            <MenuIcon size={20} />
          </button>
          <h1 className="chat-title">{displayTitle(title).text}</h1>
          <ProviderBadge config={config} disabled={busy} onSelect={switchProvider} />
        </header>
        <div className="messages">
          {messages.length === 0 ? (
            <div className="welcome">
              <span className="welcome-mark" aria-hidden="true">
                L
              </span>
              <h2>{displayName ? `Hi ${displayName}, what do you want to learn?` : "What do you want to learn?"}</h2>
              <p className="muted">
                Ask anything about Lenny's Podcast. Answers come only from the episode transcripts, with sources you can click.
              </p>
              <div className="tiles">
                {TILES.map((t) => (
                  <button key={t.title} type="button" className="tile" disabled={busy} onClick={() => setPrefill({ text: t.prefill, nonce: Date.now() })}>
                    <span className="tile-icon" aria-hidden="true">
                      {t.icon}
                    </span>
                    <strong>{t.title}</strong>
                    <span className="muted small">{t.text}</span>
                  </button>
                ))}
              </div>
              <p className="muted small examples-label">Or try one of these:</p>
              <ul className="examples">
                {suggestions.map((q) => (
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
        <Composer disabled={busy} prefill={prefill} onSend={send} />
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
