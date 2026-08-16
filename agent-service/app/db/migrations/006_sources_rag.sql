-- Living Sources: first-class sources (web in P1; facebook/instagram added in P2) + RAG store.
-- Ingest state lives as columns on `sources` (machine-written) — separate from user-edited `config`.
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector 0.8.2 (already installed in deploy; no-op there)

CREATE TABLE IF NOT EXISTS sources (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL,
  kind          text NOT NULL CHECK (kind IN ('web','facebook','instagram')),
  name          text NOT NULL,
  config        jsonb NOT NULL DEFAULT '{}'::jsonb,
  connection_id uuid,
  enabled       boolean NOT NULL DEFAULT true,
  cadence       text NOT NULL DEFAULT 'daily',
  detected_kind text,
  feed_url      text,
  last_refreshed_at timestamptz,
  last_status   text NOT NULL DEFAULT 'pending',
  last_error    text,
  next_due_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL,
  source_id    uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  url          text NOT NULL,
  title        text,
  author       text,
  published_at timestamptz,
  fetched_at   timestamptz NOT NULL DEFAULT now(),
  content_hash text NOT NULL,
  char_count   int,
  status       text NOT NULL DEFAULT 'ok'
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_org_url_uq ON documents(org_id, url);

CREATE TABLE IF NOT EXISTS chunks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ord         int  NOT NULL,
  text        text NOT NULL,
  embedding   vector(2560) NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks(document_id);
-- Exact cosine for P1. NOTE: pgvector ivfflat/hnsw cap at 2000 dims; 2560 needs `halfvec(2560)`
-- or a Matryoshka-truncated column for ANN later — out of scope here (corpus is small).

ALTER TABLE sources   ENABLE ROW LEVEL SECURITY;  ALTER TABLE sources   FORCE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;  ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE chunks    ENABLE ROW LEVEL SECURITY;  ALTER TABLE chunks    FORCE ROW LEVEL SECURITY;

CREATE POLICY src_all ON sources   USING (org_id = current_setting('app.org', true)::uuid)
                                   WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE POLICY doc_all ON documents USING (org_id = current_setting('app.org', true)::uuid)
                                   WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE POLICY chk_all ON chunks    USING (org_id = current_setting('app.org', true)::uuid)
                                   WITH CHECK (org_id = current_setting('app.org', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON sources, documents, chunks TO npo_app;

-- NOTE: the FB3 capability→sources backfill lives in 007_backfill_fb3_sources.sql. It cannot run here:
-- once FORCE RLS is on (above), an in-migration INSERT…SELECT sees no org-scoped capabilities rows and
-- the sources WITH CHECK rejects them (no app.org in a migration). 007 toggles FORCE off for the copy.
