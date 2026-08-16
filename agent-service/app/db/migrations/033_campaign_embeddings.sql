-- Semantic memory of past campaigns: one embedding per campaign brief, so planning a new campaign can
-- retrieve the org's most TOPICALLY-similar prior campaigns (not just the most recent) — to avoid proposing
-- a near-duplicate and to draw conclusions ("your summer donation pushes engaged best"). Matched the same
-- 2560-dim Qwen3-Embedding space as the RAG `chunks` table. Like `chunks`, no ANN index: pgvector
-- ivfflat/hnsw cap at 2000 dims and the per-org campaign corpus is tiny, so an exact cosine scan is fine.
CREATE TABLE IF NOT EXISTS campaign_embeddings (
  campaign_id uuid PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL,
  brief       text NOT NULL,
  embedding   vector(2560) NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE campaign_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_embeddings FORCE  ROW LEVEL SECURITY;

CREATE POLICY camp_emb_all ON campaign_embeddings
  USING      (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON campaign_embeddings TO npo_app;
