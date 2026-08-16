-- 027_campaign_refine.sql — tailored refine chips on a post + persisted caption revision history (undo).
ALTER TABLE posts ADD COLUMN IF NOT EXISTS refine_suggestions jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS post_revisions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL,
    post_id     uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    content     text NOT NULL,
    source      text NOT NULL DEFAULT 'edit',
    created_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE post_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_revisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_revisions_isolation ON post_revisions;
CREATE POLICY post_revisions_isolation ON post_revisions
    USING (org_id = current_setting('app.org', true)::uuid)
    WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, DELETE ON post_revisions TO npo_app;
CREATE INDEX IF NOT EXISTS post_revisions_post_idx ON post_revisions (org_id, post_id, created_at DESC);
