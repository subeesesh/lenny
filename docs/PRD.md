# PRD: The Lenny Growth Assistant

| | |
|---|---|
| Status | v3 (minimal) |
| Owner | Subee |
| Date | 2026-10-09 |
| Due | 2026-10-12 EOD |

**Guiding rule:** meet every requirement in the brief with the fewest moving parts. Anything not required by the brief is out unless it is cheap and removes a real risk.

## 1. Discovery brief

### 1.1 User and problem
**Primary user:** growth PM or product marketer at a startup. Secondary: a founder doing their own growth.

**Job to be done:** "Before I make a product or growth decision, or write about one, show me what experienced operators said about it, with sources I can check."

**Pain removed:**
- Hundreds of hours of transcripts; manual search is slow.
- Generic LLM answers are ungrounded and unattributable.
- Turning insights into a shareable piece (essay, one-pager) is a separate manual step.

### 1.2 Success metrics

| # | Metric | Target | How measured |
|---|---|---|---|
| M1 | Grounded questions where a cited episode is the gold episode | ≥ 80% | 30 grounded questions in `eval/eval_set.json`, eval script |
| M2 | Out-of-scope questions correctly refused | ≥ 9 of 10 | 10 out-of-scope questions, eval script |
| M3 | Essay length 1,125–1,375 words | ≥ 80% of 10 runs (cloud); local result reported separately | Word count in eval script |
| M4 | Local time to first token | < 5 s p50 | Logged `ttft_ms` |
| M5 | Fresh-clone setup | Running in ≤ 15 min from README (excluding model downloads) | Manual run |

**Eval set:** 40 questions. 30 grounded (15 fact, 10 framework, 1 attribution, 4 host-question-plus-answer) across 26 episodes, and 10 out-of-scope (6 off-topic, 2 near-domain traps, 1 false-attribution trap, 1 privacy request).

### 1.3 Assumptions
1. Single-tenant internal tool; no authentication. The user enters a display name once (stored in browser and saved as session metadata).
2. English only.
3. Source: public repo `ChatPRD/lennys-podcast-transcripts`, pinned commit `be8ab89`, 303 episode folders with one `transcript.md` each (YAML frontmatter + dialogue).
4. The evaluator has Docker and Ollama installed, with the demo models pulled.
5. A small local model gives weaker answers and essays than a cloud model. Local is the required demo path; cloud is the quality path.
6. Cloud access uses an Anthropic API key in `.env` (optional).
7. "Strictly from transcripts" means no outside knowledge in answers. Exception added at the product owner's request: when the user asks to apply the guests' advice (a plan, experiment or checklist), the answer may build one from the cited ideas, says up front that the plan is an application rather than something said on the podcast, cites a passage for every step, and adds no outside facts or numbers. Greetings and "what can you do" questions get a short fixed-style reply; any other request (coding, weather, etc.) is refused.

### 1.4 Scope

| Included | Why |
|---|---|
| Vector search (pgvector, exact) with citations | Core grounding requirement |
| Session-scoped chat with follow-ups | Required |
| Ship 30 essay skill (`SKILL.md`) | Required |
| Markdown + HTML artifacts in a sandboxed viewer | Required |
| Ollama / Anthropic toggle | Required |
| Health/ready endpoints, JSON logs, graceful errors | Required (operability) |
| Docker Compose: `db` + `api` (API also serves the built UI) | One-command start, fewest containers |

| Excluded | Why |
|---|---|
| Auth, roles, sharing | Not needed for an internal evaluation |
| Comparing chunking strategies, HNSW index | ~16.5k vectors: exact search takes milliseconds; one sensible chunker is enough |
| Hybrid search, reranker, LLM query rewriting, LLM router | Extra calls and latency; simple rules suffice |
| Delete a chat (with its messages and documents) | Added after build step 7 at the product owner's request |
| Artifact editing/versions, download, session rename | Not required |
| OpenAI provider | One cloud provider is required; one is enough |
| Ollama inside Compose | GPU passthrough is unreliable on Windows; host Ollama is documented |

### 1.5 Risks and trade-offs

| Risk | Mitigation |
|---|---|
| Hallucination | Similarity threshold → refusal; prompt requires `[n]` citations from given context only |
| Weak local model / truncated output | non-thinking qwen3 instruct build (`think: false`), `num_ctx=8192`, `max_tokens=3000`; top-5 chunks; cloud toggle for quality |
| Latency on a small GPU | SSE streaming, status messages, no extra LLM calls before answering |
| Cloud cost | Default provider is Ollama; `LLM_MAX_TOKENS` cap; token counts logged |
| Prompt injection from transcript text | Context wrapped in `<context>` and labelled untrusted; agent has no side-effecting tools |
| Unsafe artifact HTML | Server sanitizer + `sandbox=""` iframe + CSP (see architecture §7) |
| Data leakage | Secrets only in `.env`; logs redact keys; nothing leaves the machine when provider = Ollama |
| Agent SDK may not work with Ollama | Day-1 spike; fallback documented in architecture §6 |
| Dirty data (duplicates, sponsor reads, mixed formats) | Small cleaning step (architecture §4.3) with an ingest summary |

## 2. Flows

**F1: Ask.** New chat → type question → "Searching transcripts…" → answer streams with citation chips (guest, episode, timestamp link). Weak retrieval → "The transcripts don't cover this."

**F2: Follow-up.** "What did she say about pricing?" → retrieval uses the previous user question plus the new one, so the topic carries over.

**F3: Essay.** "Write a Ship 30 essay" button or phrase → essay generated with the skill → opens in the Artifact Viewer as Markdown with a sources list.

**F4: Artifact.** "Make an HTML one-pager" / "Make a markdown doc" → sanitized artifact opens beside the chat; Preview / Source / Copy.

**F5: Switch model.** Header badge → choose Local · Agent SDK (default: Ollama through the Claude Agent SDK), Local (Ollama direct) or Cloud (Anthropic) → next message uses it. Unavailable providers are greyed out with the reason.

**F6: Resume.** Sidebar lists sessions (title = first question, truncated); clicking one reloads messages, citations, artifacts.

## 3. Functional requirements

| ID | Requirement |
|---|---|
| FR1 | Create/list/get sessions; each session has independent context |
| FR2 | Persist sessions, messages, citations, artifacts, timestamps, user metadata in PostgreSQL |
| FR3 | `POST /sessions/{id}/messages` streams SSE events |
| FR4 | `make ingest`: load, clean, chunk, embed; skips unchanged episodes (content hash) |
| FR5 | Top-5 cosine search with episode/guest/URL/timestamp and score |
| FR6 | Answers cite sources; unsupported questions are refused |
| FR7 | Router: UI hint → keyword rules → default `qa` |
| FR8 | Ship 30 skill in `skills/ship30/SKILL.md`; one generation + one retry on word-count miss |
| FR9 | Artifact Viewer renders Markdown and HTML in a sandboxed iframe beside chat |
| FR10 | Provider/model switchable via `.env` and UI, no code change |
| FR11 | `/health` and `/ready` (DB, Ollama, cloud key, chunk count) |
| FR12 | JSON logs with request ID, route, provider, retrieval scores, latency |
| FR13 | Validation and structured errors on all endpoints |
| FR14 | `docker compose up` startup; `.env.example` |

## 4. Acceptance criteria

- **AC1 Grounded:** a covered question streams an answer with ≥1 citation to a relevant episode.
- **AC2 Unsupported:** "What's the weather in Paris?" → refusal, no citations.
- **AC3 Isolation:** a fact stated in session A is not used in session B (automated test).
- **AC4 Follow-up:** "give me an example of that" retrieves on the previous topic.
- **AC5 Essay:** hook, ≥3 headings, bullets, bold, closing takeaway, sources list, shown in the viewer; word count logged.
- **AC6 Artifact safety:** HTML with `<script>`, `onerror=`, `javascript:` links, `<iframe>`, `<form>` or external URLs renders with none of them executing or loading (sanitizer tests pass).
- **AC7 Toggle:** after switching provider, the next message uses it (badge + log) with no restart.
- **AC8 Resilience:** Ollama down → error naming Ollama and `ollama serve`; no API key → cloud option disabled with reason; timeout → one retry then error; DB down → `/ready` 503 and structured 503 from the API.
- **AC9 Persistence:** sessions, messages and artifacts survive `docker compose restart`.
- **AC10 Fresh clone:** README steps alone get the app answering a question.

## 5. Provider and fallback policy

There is never an automatic switch between providers.

| Situation | Behavior |
|---|---|
| Ollama unreachable / model missing | Error with the fix (`ollama serve` / `ollama pull <model>`); if a cloud key exists, the error offers a "Switch to Cloud" button. The same applies to both local paths (direct and through the Agent SDK) |
| No Anthropic key | Cloud option disabled in the UI with "Add ANTHROPIC_API_KEY to .env" |
| Any provider times out | Retry once, then a structured error with a Retry button |

Why no automatic fallback: a silent switch to cloud sends data off the machine and costs money; a silent switch to local changes answer quality without the user knowing. One click is enough.

## 6. Implementation plan

| Day | Work | Exit criteria |
|---|---|---|
| Oct 9 | Docs; Agent SDK + Ollama spike; clone corpus | Spike outcome recorded |
| Oct 10 | Compose + Postgres/pgvector; ingest (clean, chunk, embed); retrieval; `qa` route with SSE; sessions API; tests for these | AC1–AC4, AC9 |
| Oct 11 | UI (chat, sessions, badge, viewer); essay + artifact routes; sanitizer; toggle; resilience; remaining tests | AC5–AC8 |
| Oct 12 | Eval run; README; clean-clone test; agent transcripts; demo video; submit | All ACs; form submitted |

**Cut line if late:** copy button, citation popover excerpts (show chips only), eval of M3/M4. Never cut: citations, sandbox, Ollama demo, tests, docs.

## 7. Deliverables checklist

- [ ] Public repo, no secrets
- [ ] README.md
- [ ] docs/PRD.md, docs/design.md, docs/architecture.md
- [ ] docs/agent-transcripts/ (incl. failed attempts, secrets removed)
- [ ] Tests + docs/manual-test-plan.md
- [ ] Demo video (2–3 min, camera on, YouTube)
- [ ] Submission form

## 8. Open questions

1. Local model: **decided 2026-10-09: `qwen3:4b-instruct-2507-q4_K_M`.** The plain `qwen3:4b` tag now resolves to the thinking-only 2507 build; `think: false` and `/no_think` don't stop its reasoning (one cited answer streamed ~1,600 reasoning tokens and took 229 s). The instruct build is the same 4B size without a reasoning step. `llama3.2:3b` was not tried.
2. Agent SDK with Ollama: **decided by the Day-1 spike:** direct `/api/chat` for Ollama (architecture §6.3).
3. Similarity threshold: **0.69**, set from the eval set (architecture §5).
