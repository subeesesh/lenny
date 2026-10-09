CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS episodes (
  id           SERIAL PRIMARY KEY,
  slug         TEXT UNIQUE NOT NULL,
  title        TEXT NOT NULL,
  guest        TEXT,
  url          TEXT,              -- null if missing or failed validation
  published_at DATE,
  content_hash TEXT NOT NULL,
  ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id          SERIAL PRIMARY KEY,
  episode_id  INT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  ord         INT NOT NULL,
  speaker     TEXT,              -- speaker at chunk start
  start_ts    TEXT,              -- "HH:MM:SS" at chunk start, if present
  text        TEXT NOT NULL,
  embedding   vector(768) NOT NULL,
  UNIQUE (episode_id, ord)
);
-- No vector index: ~13k rows, exact cosine scan is fast enough (measured in eval).

CREATE TABLE IF NOT EXISTS sessions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title      TEXT NOT NULL DEFAULT 'New chat',   -- set from first question (first 60 chars)
  user_meta  JSONB NOT NULL DEFAULT '{}',        -- {display_name}
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id          SERIAL PRIMARY KEY,
  session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content     TEXT NOT NULL,
  route       TEXT,                       -- qa | essay | artifact | chat
  citations   JSONB NOT NULL DEFAULT '[]',-- [{chunk_id, title, guest, url, ts, score}]
  provider    TEXT,
  model       TEXT,
  status      TEXT NOT NULL DEFAULT 'complete', -- complete | error
  latency_ms  INT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_session_id_idx ON messages (session_id, id);

CREATE TABLE IF NOT EXISTS artifacts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  message_id  INT REFERENCES messages(id) ON DELETE SET NULL,
  type        TEXT NOT NULL CHECK (type IN ('markdown','html')),
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,              -- HTML is stored already sanitized
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
