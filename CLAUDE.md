# CLAUDE.md: Lenny Growth Assistant

Take-home for a Forward Deployed Engineer role. Due 2026-10-12 EOD.

## Source of truth
- `docs/PRD.md`, `docs/architecture.md`, `docs/design.md`. Follow them. If code must differ, update the doc in the same change and say why.
- `eval/eval_set.json` is fixed; do not edit questions.

## Golden rules
- **Minimal.** Meet the requirement, nothing more. No extra abstractions, no plugin systems, no features outside the PRD. If unsure, ask instead of building.
- Small, working steps. After each step, run the tests and fix them before moving on.
- Never commit secrets. Only `.env.example` is committed; `.env` and `data/` are git-ignored.
- Never add an automatic provider switch (PRD §5).
- Artifacts always render in `<iframe sandbox="">` with the CSP from architecture §7. Never relax this.

## Stack
- Backend: Python 3.12, FastAPI, `psycopg[binary]` + `psycopg_pool` (no ORM), `pgvector`, `pydantic-settings`, `structlog`, `httpx`, `nh3`, `langchain-text-splitters` (splitter only), `claude-agent-sdk`, `pytest`, `pytest-asyncio`.
- DB: `pgvector/pgvector:pg16`. Schema in `backend/schema.sql`, applied on startup.
- Frontend: Vite + React + TypeScript, plain CSS, `marked`. Built into static files served by FastAPI.
- Models: Ollama on the host (`qwen3:4b-instruct-2507-q4_K_M`, a non-thinking build, with `think: false` and `num_ctx=8192`; `nomic-embed-text` with `search_document: ` / `search_query: ` prefixes). Cloud: Anthropic.

## Layout
```
backend/app/{api,agent,llm,retrieval,ingest,db,security}/   backend/skills/{qa,ship30,artifact}/SKILL.md
backend/tests/   web/   eval/   docs/   docker-compose.yml   Makefile   .env.example   README.md
```

## Commands
- `make up` → `docker compose up -d --build` (open http://localhost:8000)
- `make ingest` → run ingestion inside the api container
- `make test` → `pytest` (LLM and embeddings mocked; DB tests use the compose DB)
- `make eval` → `python eval/run_eval.py`

## Conventions
- Errors: always `{"error":{"code","message","request_id"}}`, codes from architecture §3.
- Every DB query on messages/artifacts filters by `session_id`.
- Log with structlog; never log API keys or full message text.
- Keep functions short; type hints everywhere; no comments that restate the code.
