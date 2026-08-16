-- 028_post_metrics.sql — per-post performance snapshots + daily follower snapshots + insights refresh throttle.
CREATE TABLE IF NOT EXISTS post_metrics (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           uuid NOT NULL,
    post_id          uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    connection_id    uuid,
    provider         text NOT NULL,
    external_post_id text,
    captured_at      timestamptz NOT NULL DEFAULT now(),
    metrics          jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE post_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_metrics FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_metrics_isolation ON post_metrics;
CREATE POLICY post_metrics_isolation ON post_metrics
    USING (org_id = current_setting('app.org', true)::uuid)
    WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON post_metrics TO npo_app;
CREATE INDEX IF NOT EXISTS post_metrics_post_idx ON post_metrics (org_id, post_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS audience_snapshots (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL,
    connection_id uuid,
    provider      text NOT NULL,
    captured_at   timestamptz NOT NULL DEFAULT now(),
    followers     integer NOT NULL DEFAULT 0
);
ALTER TABLE audience_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE audience_snapshots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audience_snapshots_isolation ON audience_snapshots;
CREATE POLICY audience_snapshots_isolation ON audience_snapshots
    USING (org_id = current_setting('app.org', true)::uuid)
    WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON audience_snapshots TO npo_app;
CREATE INDEX IF NOT EXISTS audience_snapshots_idx ON audience_snapshots (org_id, provider, captured_at DESC);

ALTER TABLE org_settings ADD COLUMN IF NOT EXISTS insights_refreshed_at timestamptz;
