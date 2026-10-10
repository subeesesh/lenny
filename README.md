# Lenny Growth Assistant

A chat assistant that answers questions about **Lenny's Podcast** strictly from the episode transcripts, with clickable sources, and turns what the guests said into a **Ship 30 for 30 essay** or an **HTML one-pager**. It runs fully local on Ollama by default; Anthropic Claude is an optional cloud provider you switch to with one click (never automatically).

- **Ask:** answers stream with `[n]` citations and source chips that link to the YouTube timestamp. Questions the transcripts don't cover get "The transcripts don't cover this."
- **Write a Ship 30 essay:** a ~1,250-word atomic essay grounded in 10 passages, with a sources list, opened in a side viewer.
- **Make a one-pager:** a styled HTML (or Markdown) document, sanitized on the server and rendered in a sandboxed iframe.
- Sessions, messages, citations and documents are stored in PostgreSQL and survive restarts.

Product and design decisions: [docs/PRD.md](docs/PRD.md) · [docs/architecture.md](docs/architecture.md) · [docs/design.md](docs/design.md) · [docs/manual-test-plan.md](docs/manual-test-plan.md) · [eval/results.md](eval/results.md) · build log with the coding agent: [docs/agent-transcripts/](docs/agent-transcripts/)

## Architecture

```
Browser (React UI, served by the API) ──HTTP/SSE──▶ FastAPI (Docker: api)
                                                      ├─ router ─▶ skill: qa | essay | artifact | chat  (backend/skills/*/SKILL.md)
                                                      │              └─ llm adapter ─▶ Ollama on the host (default)
                                                      │                              └▶ Anthropic via Claude Agent SDK (optional)
                                                      ├─ retrieval: guards → nomic-embed-text query → pgvector cosine top-15
                                                      │             → ≤4 per episode → top 5 (essays: 10) → threshold 0.69
                                                      └─ repositories ─▶ PostgreSQL 16 + pgvector (Docker: db)
Ingestion (CLI): git clone transcripts → clean → chunk (~1,800 chars) → embed → 289 episodes, 16,461 chunks
```

Retrieval runs before generation (citations are sent before the first token, and weak retrieval is refused without calling the model). Generated HTML is sanitized with `nh3` and every document renders in `<iframe sandbox="">` with a strict CSP. Details: [architecture.md](docs/architecture.md).

## Prerequisites

- **Docker** with Compose v2 (Docker Desktop on Windows/macOS).
- **Ollama** running on the host: <https://ollama.com/download>.
- ~4 GB free disk for models and images. A GPU helps a lot but is not required.
- Optional: an Anthropic API key for the cloud provider.
- Optional: `make`. Every `make` target below also has the plain command (Windows usually has no `make`).

## Setup

```bash
git clone https://github.com/subeesesh/lenny.git lenny-growth-assistant
cd lenny-growth-assistant
cp .env.example .env                      # Windows PowerShell: Copy-Item .env.example .env

ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull nomic-embed-text

make up                                   # or: docker compose up -d --build
make ingest                               # or: docker compose exec api python -m app.ingest
```

Then open **http://localhost:8000**, enter a display name, and ask a question.

- The first `make up` builds the images (a few minutes; it downloads Python and Node dependencies).
- `make ingest` clones the transcripts repo at the pinned commit into `data/transcripts`, then embeds 16,461 chunks: about **9 minutes with a GPU**, longer on CPU. It prints a summary when done. If `failures` is not 0 (for example Ollama was briefly overloaded and returned errors for a few episodes), run `make ingest` again: it skips unchanged episodes and only retries the missing ones (`chunks_in_db` should end at 16,461). For a quick check first: `make ingest ARGS="--limit 5"`.
- `GET http://localhost:8000/api/v1/ready` shows `{db, ollama, anthropic_key, chunks}`.
- If port 5432 is already used on your machine (a local PostgreSQL), set `DB_HOST_PORT=5433` in `.env` before `make up`. The app itself talks to the database inside Docker; the host port is only for debugging.

| Command | Plain equivalent | What it does |
|---|---|---|
| `make up` | `docker compose up -d --build` | Build and start `db` + `api` |
| `make ingest` | `docker compose exec api python -m app.ingest` | Load, clean, chunk and embed the transcripts |
| `make test` | `docker compose exec api pytest` | Run the test suite (needs `make up`) |
| `make eval` | `python eval/run_eval.py` | Run the eval set against the running app |
| `make down` | `docker compose down` | Stop (data stays in the `pgdata` volume) |

## Switching to Anthropic (cloud)

1. Put your key in `.env`: `ANTHROPIC_API_KEY=sk-ant-...` (optionally change `ANTHROPIC_MODEL`).
2. Restart the API: `docker compose up -d` (env changes need the container recreated).
3. In the app, click the provider badge in the header and choose **Cloud**. The next message uses it; the badge and the `turn_done` log line show which provider answered.

Without a key, Cloud is shown disabled with the reason. The app never switches provider on its own: when Ollama fails, the error card offers **Retry** and, if a key is configured, **Switch to Cloud** (PRD §5).

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | Provider at startup: `ollama` or `anthropic` |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama as seen from the container |
| `OLLAMA_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Chat model. Use this instruct build: the plain `qwen3:4b` tag is a thinking-only model that ignores `think: false` |
| `OLLAMA_NUM_CTX` | `8192` | Context window |
| `OLLAMA_NUM_GPU` | empty | Layers on the GPU; empty lets Ollama decide. See [Performance](#performance-on-small-gpus) |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model (768-d) |
| `ANTHROPIC_API_KEY` | empty | Enables the cloud provider |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Cloud model |
| `LLM_MAX_TOKENS` | `3000` | Max tokens per generation |
| `LLM_TIMEOUT_S` | `120` | Idle timeout (no data for this long); retried once if nothing was streamed yet |
| `RETRIEVAL_TOP_K` | `5` | Passages per answer (essays use 10) |
| `RETRIEVAL_MIN_SCORE` | `0.69` | Below this top cosine similarity the answer is "not covered" (tuned on the eval set) |
| `DATABASE_URL` | `postgresql://lenny:lenny@db:5432/lenny` | Database URL inside Docker |
| `LOG_LEVEL` | `INFO` | JSON logs via structlog |
| `DB_HOST_PORT` | `5432` | Host port for the database container |

## Performance on small GPUs

Measured on a laptop with a 4 GB RTX 3050 and 16 GB RAM (details: [architecture §9](docs/architecture.md#9-resilience)). With Ollama's defaults the chat model and the embedding model evict each other on every question (~12 s of loading per answer). These settings fix that with no change in answers:

1. Ollama server environment (Windows: user environment variables, then quit and restart Ollama from the tray):
   - `OLLAMA_KV_CACHE_TYPE=q8_0` (8-bit KV cache, halves its memory)
   - `OLLAMA_MAX_LOADED_MODELS=2` (keep the embedder and the chat model loaded together)
2. In `.env`: `OLLAMA_NUM_GPU=32`, then `docker compose up -d`.

Result: first token ~1.9 s (p50 over the eval set), a full answer ~8 s, a one-pager ~1 min, an essay ~3 min. On a bigger GPU, leave `OLLAMA_NUM_GPU` empty.

## Tests and eval

- `make test`: 115 pytest tests run inside the `api` container against a separate `lenny_test` database built from fixture transcripts; the LLM and embeddings are mocked, so no model is needed. They cover the error shape, `/health` and `/ready`, each ingestion rule, retrieval and both guards, the providers (Ollama down, model missing, timeout + one retry, no key), the router, SSE order, session isolation, the XSS payload list and the essay retry. List per file: [architecture §11](docs/architecture.md#11-tests-pytest-llm-and-embeddings-mocked).
- `make eval`: runs the 40 questions in `eval/eval_set.json` (30 grounded, 10 out of scope) plus 10 essays through the running app and writes `eval/results.md`. Add `--essays 0` to skip the essays (~6 min instead of ~35 min locally).

Latest local results ([eval/results.md](eval/results.md)):

| Metric | Target | Local (qwen3 4B instruct) |
|---|---|---|
| M1 gold episode among the cited sources | ≥ 80% | 30/30 |
| M2 out-of-scope questions refused | ≥ 9/10 | 10/10 |
| M3 essay 1,125–1,375 words | ≥ 80% on cloud; local reported | 4/10 (misses within ~60 words) |
| M4 time to first token, p50 | < 5 s | 1.9 s (with the settings above) |

The results also include a threshold sweep, the tuning history and an accuracy audit of the generated text. Manual UI checks: [docs/manual-test-plan.md](docs/manual-test-plan.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Ollama is not reachable … Run `ollama serve`" | Start Ollama (tray app or `ollama serve`), then click **Retry**. Check `curl http://localhost:11434/api/tags`. |
| "The model … is not pulled. Run `ollama pull …`" | Run the command shown; `/config` and the provider menu show the same reason. |
| Cloud is disabled in the provider menu | Add `ANTHROPIC_API_KEY` to `.env` and run `docker compose up -d`. |
| `make up` fails with "ports are not available … 5432" | Another PostgreSQL uses 5432: set `DB_HOST_PORT=5433` in `.env`. |
| `/ready` returns 503 or requests fail with `db_unavailable` | `docker compose ps` and `docker compose logs db`; `docker compose up -d` starts it again (the API waits for the DB healthcheck). |
| Every question gets "The transcripts don't cover this." | `make ingest` hasn't run or failed: check `chunks` in `/ready` (should be 16,461). |
| Slow first answer | The first question loads the models (~5–10 s). Ollama unloads idle models after a while; the app asks it to keep them for 30 min. On small GPUs apply [Performance](#performance-on-small-gpus). |
| "out of memory" / `cudaMalloc failed` / `llama-server … terminated` in an error card | The model didn't fit when loading. Close GPU-heavy apps or restart Ollama, then Retry. On a 4 GB GPU use the [Performance](#performance-on-small-gpus) settings. On Windows with 16 GB RAM, Docker's WSL VM can hold several GB: cap it in `%USERPROFILE%\.wslconfig` with `[wsl2]` / `memory=3GB`, then `wsl --shutdown` and restart Docker Desktop. When restarting Ollama on Windows also end any leftover `llama-server.exe`. |
| `make: command not found` (Windows) | Use the plain commands in the table above. |
| Scripts against `http://localhost:8000` are slow on Windows | Python resolves `localhost` to IPv6 first and waits ~2 s per request; use `http://127.0.0.1:8000` (the eval script already does). Browsers are not affected. |

## Extending

**Add a skill** (for example a LinkedIn post):
1. Write `backend/skills/<name>/SKILL.md` with the instructions and output format; skills are loaded at startup.
2. Add `run_<name>` in `backend/app/agent/` following `essay.py`: retrieve, call `start_generation`, `generate(provider, skills["<name>"], messages)`, then set `result.text` (and `result.artifact` to save a document).
3. Route to it: keywords in `backend/app/agent/router.py` and the dispatch table in `run_turn` (`backend/app/agent/skills.py`); allow the new `route_hint` in `MessageCreate` (`backend/app/api/sessions.py`) if the UI gets a button.
4. Add tests next to `backend/tests/test_artifacts.py` using `FakeProvider`/`FakeRetriever` from `tests/fakes.py`.

**Add a provider:**
1. Implement the `Provider` protocol (`backend/app/llm/base.py`): `name`, `model` and `stream(system, messages)` yielding text; raise `AppError("provider_unavailable", …)` or `ProviderTimeout` on failure (`stream_with_retry` handles the one retry).
2. Wire it in `make_provider` and `provider_statuses` (`backend/app/llm/providers.py`) and add its name to `LLM_PROVIDER` / `ConfigUpdate` (`backend/app/api/config.py`).
3. Add settings to `backend/app/config.py` and `.env.example`, and tests like `backend/tests/test_llm.py` using `httpx.MockTransport`.

## Project layout

```
backend/app/{api,agent,llm,retrieval,ingest,db,security}/   FastAPI app
backend/skills/{qa,ship30,artifact}/SKILL.md                 skill prompts
backend/tests/                                               pytest (fixtures in tests/fixtures/)
backend/schema.sql                                           applied on startup
web/                                                         Vite + React + TypeScript UI
eval/                                                        eval_set.json, run_eval.py, results.md
docs/                                                        PRD, architecture, design, test plan, agent transcripts
spike/                                                       Day-1 Claude Agent SDK + Ollama spike
```
