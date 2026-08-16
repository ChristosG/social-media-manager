-- Comments + AI replies (Item 7, Phase 3).
-- comments: inbox of comments pulled from the org's published FB Page posts + IG media, with the
--   drafted/posted AI reply. Idempotent ingest via unique(org_id, provider, external_id); exactly-once
--   reply via reply_external_id (never double-reply). FORCE RLS on org_id like every table.
-- org_settings: small per-org settings row (one per org). Home for the auto-reply toggle + the comment
--   poll throttle timestamp. Kept out of memory_entries (which has a kind allow-list + is surfaced to the
--   agent as brand knowledge) so settings never leak into generation context.

CREATE TABLE IF NOT EXISTS comments (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             uuid        NOT NULL,
  connection_id      uuid        NOT NULL,
  provider           text        NOT NULL,                 -- 'facebook' | 'instagram'
  external_id        text        NOT NULL,                 -- provider comment id
  post_external_id   text,                                 -- the post/media the comment is on
  scheduled_post_id  uuid        NULL REFERENCES scheduled_posts(id) ON DELETE SET NULL,
  author_name        text,
  author_external_id text,
  message            text        NOT NULL DEFAULT '',
  permalink          text,
  commented_at       timestamptz,                          -- provider timestamp
  status             text        NOT NULL DEFAULT 'open',  -- open | replied | ignored
  reply_text         text        NOT NULL DEFAULT '',      -- the drafted/posted reply
  reply_external_id  text,                                 -- provider id of our posted reply
  reply_mode         text,                                 -- 'draft' | 'auto'
  replied_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, provider, external_id)
);

ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments FORCE ROW LEVEL SECURITY;
CREATE POLICY comments_isolation ON comments
  USING     (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE INDEX IF NOT EXISTS comments_inbox ON comments (org_id, status, commented_at DESC);
CREATE INDEX IF NOT EXISTS comments_conn_time ON comments (org_id, connection_id, commented_at DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON comments TO npo_app;

CREATE TABLE IF NOT EXISTS org_settings (
  org_id             uuid        PRIMARY KEY,
  auto_reply_safe    boolean     NOT NULL DEFAULT false,   -- auto-post classifier-safe replies
  comments_polled_at timestamptz,                          -- last comment poll (ingest throttle)
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE org_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY org_settings_isolation ON org_settings
  USING     (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON org_settings TO npo_app;
