-- Imported posts: posts pulled from a connected Meta account that were NOT created/published through
-- Social Studio. They land in the ledger as origin='imported', status='posted', carrying the Meta object
-- id so we can (a) dedup re-imports and (b) link per-post metrics. The partial unique index dedups on the
-- external id while leaving app-created posts (external_post_id NULL) unconstrained.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS external_post_id text;

CREATE UNIQUE INDEX IF NOT EXISTS posts_org_external_uniq
  ON posts(org_id, external_post_id) WHERE external_post_id IS NOT NULL;

-- Widen the origin whitelist for the two new sources: 'imported' (pulled from a connected Meta account)
-- and 'custom' (a draft the user typed directly into a campaign, Phase 3).
ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_origin_check;
ALTER TABLE posts ADD CONSTRAINT posts_origin_check
  CHECK (origin IN ('agent_suggested','user_requested','imported','custom'));
