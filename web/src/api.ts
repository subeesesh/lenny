const BASE = "/api/v1";

export type Citation = {
  chunk_id: number;
  slug: string;
  title: string;
  guest: string | null;
  url: string | null;
  ts: string | null;
  score: number;
};

export type ArtifactRef = { id: string; type: "markdown" | "html"; title: string };
export type Artifact = ArtifactRef & { content: string; session_id: string; message_id: number | null };

export type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  route: string | null;
  citations: Citation[];
  provider: string | null;
  model: string | null;
  status: "complete" | "error";
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  user_meta?: { display_name?: string };
};
export type SessionDetail = SessionSummary & {
  messages: Message[];
  artifacts: (ArtifactRef & { message_id: number | null })[];
};

export type ProviderStatus = { name: string; label: string; model: string; available: boolean; reason: string | null };
export type Config = { active: { provider: string; model: string }; providers: ProviderStatus[] };

export type ErrorBody = { code: string; message: string; request_id: string };

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

/** Thrown when the server can't be reached at all (shows the top banner). */
export class NetworkError extends Error {}

async function request(method: string, path: string, body?: unknown): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new NetworkError("The server is not reachable.");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { error?: ErrorBody } | null;
    throw new ApiError(data?.error?.code ?? "internal_error", data?.error?.message ?? `Request failed (${res.status}).`);
  }
  return res;
}

async function json<T>(method: string, path: string, body?: unknown): Promise<T> {
  return (await request(method, path, body)).json() as Promise<T>;
}

export const api = {
  sessions: () => json<SessionSummary[]>("GET", "/sessions"),
  session: (id: string) => json<SessionDetail>("GET", `/sessions/${id}`),
  createSession: (displayName: string) =>
    json<{ id: string; title: string }>("POST", "/sessions", { user_meta: { display_name: displayName } }),
  deleteSession: async (id: string) => {
    await request("DELETE", `/sessions/${id}`);
  },
  config: () => json<Config>("GET", "/config"),
  setProvider: (provider: string) => json<Config>("PUT", "/config", { provider }),
  artifact: (id: string, sessionId: string) =>
    json<Artifact>("GET", `/artifacts/${id}?session_id=${encodeURIComponent(sessionId)}`),
};

export type StreamEvent =
  | { event: "status"; data: { stage: "retrieving" | "generating" } }
  | { event: "citations"; data: Citation[] }
  | { event: "token"; data: { text: string } }
  | { event: "artifact"; data: ArtifactRef }
  | {
      event: "done";
      data: { message_id: number; provider: string | null; model: string | null; latency_ms: number; retrieval_top_score: number | null };
    }
  | { event: "error"; data: ErrorBody };

function parseBlock(block: string): StreamEvent | null {
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  return event ? ({ event, data: JSON.parse(data) } as StreamEvent) : null;
}

export async function sendMessage(
  sessionId: string,
  content: string,
  routeHint: "essay" | "artifact" | null,
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  const res = await request("POST", `/sessions/${sessionId}/messages`, { content, route_hint: routeHint });
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const parsed = parseBlock(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      if (parsed) onEvent(parsed);
    }
  }
}
