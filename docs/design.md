# Design: The Lenny Growth Assistant

Status: v3 (minimal) · 2026-10-09

## 1. Principles
1. **Trust first.** Every answer shows its sources; unsupported questions get a plain "not covered."
2. **No AI plumbing.** Users see actions ("Write essay", "Make one-pager"), not prompts or routes.
3. **Always show state.** Searching, writing, failed: each is visible.
4. **Chat and artifact side by side.**
5. **Visible safety.** The provider in use and what the viewer blocks are always shown.
6. **Keyboard and screen-reader usable.**

## 2. Layout

```
App
├── Sidebar: New chat · session list (title, relative time)
├── Chat
│   ├── Header: session title · provider badge ("Local · qwen3:4b-instruct" / "Cloud · Claude")
│   ├── Messages: user / assistant · citation chips · artifact cards · status line
│   └── Composer: textarea · Send · quick actions (Write Ship 30 essay · Make one-pager)
└── Artifact pane (opens when an artifact exists)
    ├── Title · type · Preview/Source · Copy · Close
    └── Sandboxed preview + note "Sandboxed: scripts, forms, links and external content are blocked"
```

On first visit a small dialog asks for a display name (saved in the browser and sent with each new session).

## 3. Responsive

| Width | Layout |
|---|---|
| ≥ 1024 px | Sidebar 240 px · chat · artifact pane 45% |
| < 1024 px | Sidebar becomes a drawer (menu button); artifact opens as a full-screen sheet with Back |

Chat text max width ~72 characters; composer stays at the bottom.

## 4. Components

| Component | Behavior |
|---|---|
| Provider badge | Pill with icon + text; click opens a menu listing Ollama and Anthropic with "available" or the reason it isn't |
| Citation chip | `[1] Guest — Episode` link to YouTube at the timestamp (plain text if no URL); inline `[n]` in the answer match chip numbers |
| Artifact card | In-chat card with title, type and Open button |
| Status line | "Searching transcripts…" → "Writing…" |
| Empty state | One line on what the assistant does + 3 example questions |
| Not-covered answer | Neutral callout: "The transcripts don't cover this." |

## 5. States

| Situation | Treatment |
|---|---|
| Sending | User message appears immediately; composer disabled until done |
| Streaming | Tokens append; status line; screen reader announces only "Answer complete" |
| Not covered | Callout, no chips |
| Ollama down | Error card: "Can't reach Ollama. Run `ollama serve`." + Retry (+ Switch to Cloud if configured) |
| No API key | Cloud option disabled: "Add ANTHROPIC_API_KEY to .env" |
| Timeout | "The model took too long." + Retry |
| Essay / artifact generating | Status line; pane opens when ready |
| Artifact rejected | Notice with reason; chat continues |
| Sessions loading / empty / error | Skeleton / "No chats yet" / message with Retry |
| Server unreachable | Top banner with Retry |

## 6. Artifact viewer
- Markdown and HTML both render inside a sandboxed iframe (no scripts, no network, no forms, no navigation). The page itself can never be affected by artifact content.
- Markdown uses a readable serif style inside the iframe.
- Preview / Source toggle; Source is plain monospace text. Copy copies the source.
- Trade-off: links inside artifacts don't open (sandbox blocks navigation). Acceptable for documents; sources are also clickable as chips in the chat.

## 7. Visual style
- Calm, content-first. Light and dark via CSS variables following `prefers-color-scheme`.
- System sans for UI; serif for artifact bodies.
- Neutral surfaces, one accent colour; status always uses icon + text, never colour alone.
- 4 px spacing scale; line height 1.6 in messages. Motion limited to short fades, off under `prefers-reduced-motion`.

## 8. Accessibility
- WCAG AA contrast in both themes; visible focus rings.
- `Enter` sends, `Shift+Enter` new line, `Esc` closes the artifact pane/sheet.
- Landmarks: `nav` sidebar, `main` chat, `aside` artifact pane. One polite live region for status and completion.
- Chips are links with labels like "Source 1: Guest, Episode title". Iframe has a descriptive `title`.
- Touch targets ≥ 44 px; works at 200% zoom.

## 9. Microcopy
- Plain, concise, no hype. Errors say what happened and what to do, with a copyable command.
- Quick actions are outcomes: "Write a Ship 30 essay", "Make a one-pager".

## 10. Decisions

| Decision | Why | Trade-off |
|---|---|---|
| Side-by-side artifact pane | Matches the Claude Artifacts model; conversation stays visible | Sheet on small screens |
| Everything in a `sandbox=""` iframe | One simple, strong isolation rule | No interactive HTML, links don't navigate |
| Always-visible provider badge | Local vs cloud affects privacy, cost and quality | A bit of header space |
| Explicit "not covered" | Prevents made-up answers | Less chatty |
| Two breakpoints only | Less to build and test | Tablet layout is the mobile one |

## 11. Manual test plan (summary; full list in `docs/manual-test-plan.md`)
1. Enter name → new chat → covered question → answer with chips.
2. Out-of-scope question → "not covered", no chips.
3. Follow-up uses previous topic.
4. Essay button → status → artifact opens; word count in logs.
5. "Make an HTML one-pager" → renders; a crafted `<script>` payload does nothing.
6. Switch provider → badge and logs show the new one.
7. Stop Ollama → error with fix; restart → Retry works.
8. Empty API key → cloud disabled with reason.
9. 375 px width → drawer and sheet work.
10. Keyboard-only pass of 1–4; screen reader announces completion and errors.
11. Reload → sessions, messages, artifacts still there.
