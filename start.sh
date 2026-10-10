#!/usr/bin/env bash
# One-step start for macOS/Linux: ./start.sh  (safe to re-run; see README "Quick start")
set -euo pipefail
cd "$(dirname "$0")"

CHAT_MODEL="qwen3:4b-instruct-2507-q4_K_M"
EMBED_MODEL="nomic-embed-text"
URL="http://localhost:8000"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Docker and Ollama"
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop (or the Docker daemon) and run ./start.sh again."
command -v ollama >/dev/null 2>&1 || fail "Ollama is not installed. Get it from https://ollama.com/download and run ./start.sh again."
curl -sf http://127.0.0.1:11434/api/tags >/dev/null || fail "Ollama is not running. Start the Ollama app (or 'ollama serve') and run ./start.sh again."

step "Preparing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
if [ -z "$(docker compose ps -q db 2>/dev/null)" ] && grep -q '^DB_HOST_PORT=5432$' .env \
   && (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then
  sed -i.bak 's/^DB_HOST_PORT=5432$/DB_HOST_PORT=5433/' .env && rm -f .env.bak
  echo "Port 5432 is in use on this machine; the database container will use 5433 instead."
fi

step "Pulling models (skipped if already present)"
for model in "$CHAT_MODEL" "$EMBED_MODEL"; do
  ollama list | grep -q "^${model}" || ollama pull "$model"
done
ollama create lenny-qwen3-4b -f ollama/Modelfile >/dev/null || fail "Could not create the local chat model (ollama create lenny-qwen3-4b -f ollama/Modelfile)."
echo "Local chat model lenny-qwen3-4b is ready (8192 context, for the Agent SDK path)."

step "Building and starting the app (first run takes a few minutes)"
docker compose up -d --build

step "Waiting for the API"
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/api/v1/ready >/dev/null && break
  sleep 2
done
curl -sf http://127.0.0.1:8000/api/v1/ready >/dev/null || fail "The API did not become ready. See: docker compose logs api"

step "Loading transcripts (first run ~10 min with a GPU; later runs skip unchanged episodes)"
for attempt in 1 2; do
  summary="$(docker compose exec -T api python -m app.ingest | grep -v '"level"' || true)"
  echo "$summary"
  echo "$summary" | grep -Eq '^failures +0$' && break
  if [ "$attempt" = 1 ]; then echo "Some episodes failed (Ollama was busy); retrying only those."; fi
done

step "Ready: $URL"
echo "Tip for small GPUs: see README 'Performance on small GPUs' for faster answers."
if command -v open >/dev/null 2>&1; then open "$URL"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"; fi
