-- Per-conversation "current post draft": the clean caption (from draft_post) + the latest generated
-- image ids. Lets the publish Preview bind to the real post instead of scraping chat message prose.
CREATE TABLE IF NOT EXISTS conversation_drafts (
  conversation_id uuid PRIMARY KEY,
  org_id          uuid NOT NULL,
  caption         text   NOT NULL DEFAULT '',
  image_ids       uuid[] NOT NULL DEFAULT '{}',
  updated_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE conversation_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY conversation_drafts_isolation ON conversation_drafts
  USING     (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_drafts TO npo_app;
