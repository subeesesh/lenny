# Build prompts for Claude Code

Paste one prompt at a time. Finish each step (tests pass, you've checked it) before the next.
After each session, run `/export` in Claude Code and save it to `docs/agent-transcripts/NN-step-name.md` (remove any keys). Keep failed attempts too; the brief asks for them.

---

## 0. Setup (you, before Claude Code)
```bash
mkdir lenny-growth-assistant && cd lenny-growth-assistant && git init
mkdir -p docs/agent-transcripts eval
# copy PRD.md architecture.md design.md into docs/, eval_set.json into eval/, CLAUDE.md into the root
ollama pull qwen3:4b && ollama pull nomic-embed-text
claude
```

## 1. Spike: Agent SDK with Ollama (≤ 1 hour)
```
Read CLAUDE.md and docs/architecture.md §6.3. Create spike/agent_sdk_ollama.py that uses the Python claude-agent-sdk
query() with ANTHROPIC_BASE_URL=http://localhost:11434 and model qwen3:4b to answer one question, with one in-process
custom tool `search_transcripts` that returns a fixed string. Report: does it run, does the tool get called, latency.
Then do the same against Anthropic if ANTHROPIC_API_KEY is set. Don't build anything else. Write the result into
docs/architecture.md §6.3 (keep or switch to the direct /api/chat fallback).
```

## 2. Skeleton, config, DB, health
```
Following CLAUDE.md and docs/architecture.md §1–3, §6.4, §10: create the repo skeleton, .gitignore, .env.example,
docker-compose.yml (db + api), backend Dockerfile (Python 3.12 + Node for the Agent SDK), Makefile, pydantic-settings
config, backend/schema.sql applied on startup, a psycopg pool, request-ID middleware, structured error handler,
structlog JSON logs, GET /health and GET /ready. Add tests for /health, /ready with DB down (503), and the error shape.
Run `make up` and `make test`.
```

## 3. Ingestion
```
Implement architecture §4 in backend/app/ingest: clone the transcripts repo at commit be8ab89 into data/transcripts,
parse frontmatter, the cleaning rules in §4.3, the chunker in §4.4, embeddings via Ollama nomic-embed-text with the
search_document prefix in batches, hash-based skip, and the printed summary. Wire `make ingest`. Tests with small
fixture files: each speaker-header format, sponsor paragraph removed (and a normal sentence containing "sponsor"
kept), duplicate dropped, re-run skips. Mock embeddings in tests. First run it on 5 episodes, show me the chunks, then on all.
```

## 4. Retrieval
```
Implement architecture §5 in backend/app/retrieval: query embedding with the search_query prefix, cosine top-15 →
max 2 per episode → top 5, RETRIEVAL_MIN_SCORE threshold, follow-up query = previous user message + current, and the
two guards (personal-data requests, non-guest person). Tests: known quote finds the right episode (use a fixture DB),
out-of-scope returns empty, both guards.
```

## 5. LLM adapters, sessions and the qa route
```
Implement backend/app/llm (Ollama and Anthropic per the spike result; thinking off for qwen3, num_ctx from config,
timeout + one retry, clear errors for Ollama down / model missing / no key), GET/PUT /config, the session endpoints,
and POST /sessions/{id}/messages with SSE events in the order in architecture §3. Implement the router (§6.1) and the
qa and chat skills with skills/qa/SKILL.md. Persist messages with citations, provider, model, latency. Set the session
title from the first question. Tests (LLM mocked): session isolation, SSE order, 422 validation, provider unavailable,
timeout retry, router table.
```

## 6. Essay and artifact skills + sanitizer
```
First read https://www.ship30for30.com/ guide content I paste below and write skills/ship30/SKILL.md with the principles
(cite the source). Then implement the essay skill (one generation, one retry if outside 1,125–1,375 words, sources list,
saved as a markdown artifact) and the artifact skill with skills/artifact/SKILL.md, the nh3 sanitizer and 200 KB cap
from architecture §7, and GET /artifacts/{id}. Tests: XSS payload list is stripped, size cap, essay retry is triggered.
[paste the Ship 30 guide text here]
```

## 7. Frontend
```
Build web/ per docs/design.md: display-name dialog, sidebar with sessions, chat with SSE streaming, status line,
citation chips, not-covered callout, error cards with Retry / Switch to Cloud, provider badge + menu from /config,
quick actions, artifact pane (Preview/Source/Copy) rendering both markdown and html inside iframe sandbox="" with the
CSP meta, the two breakpoints, keyboard shortcuts and ARIA from design §8. Plain CSS with light/dark variables.
Serve the built files from FastAPI via a multi-stage Dockerfile. Keep it simple: no state library, no UI kit.
```

## 8. Eval + manual test plan
```
Write eval/run_eval.py that runs every eval_set item through the API and reports M1 (gold episode cited), M2 (refusals),
M3 (essay word count over 10 topics), M4 (ttft p50), plus retrieval latency. Save results to eval/results.md.
Use it to tune RETRIEVAL_MIN_SCORE. Write docs/manual-test-plan.md from design §11.
```

## 9. README and fresh-clone check
```
Write README.md: what it is, architecture diagram, prerequisites, setup (copy .env.example, ollama pull, make up,
make ingest), switching to Anthropic, env var table, tests, eval results, troubleshooting (Ollama down, model missing,
no key, DB, slow first answer), how to extend (add a skill, add a provider), and links to docs. Then clone the repo into
a temp folder and follow the README exactly; fix anything that fails.
```

## 10. You
- Run `git log` / `git grep -i "sk-ant"` to check for secrets, push a public repo.
- Record the 2–3 min video (camera on): problem → demo on Ollama → essay + artifact → one trade-off (e.g. exact search vs index, or no automatic cloud fallback). Upload to YouTube.
- Submit the form.
