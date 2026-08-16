-- Publishing pipeline: scheduled_posts + notifications + posts.image_ids (multi-image).
-- scheduled_posts: queue of org-owned posts to be published at a future time.
-- notifications: in-app inbox for publish confirmations, errors, and system events.
-- posts.image_ids: replaces the single image_id with an ordered array of image UUIDs.

ALTER TABLE posts ADD COLUMN IF NOT EXISTS image_ids uuid[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS scheduled_posts (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid        NOT NULL,
  targets       jsonb       NOT NULL,
  caption       text        NOT NULL DEFAULT '',
  image_ids     uuid[]      NOT NULL DEFAULT '{}',
  content_hash  text        NOT NULL,
  scheduled_at  timestamptz NOT NULL,
  status        text        NOT NULL DEFAULT 'pending',
  attempts      int         NOT NULL DEFAULT 0,
  result        jsonb       NOT NULL DEFAULT '{}',
  post_id       uuid        NULL REFERENCES posts(id) ON DELETE SET NULL,
  created_by    uuid        NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE scheduled_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_posts FORCE ROW LEVEL SECURITY;
CREATE POLICY scheduled_posts_isolation ON scheduled_posts
  USING     (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE INDEX IF NOT EXISTS scheduled_posts_due ON scheduled_posts (scheduled_at) WHERE status = 'pending';
GRANT SELECT, INSERT, UPDATE, DELETE ON scheduled_posts TO npo_app;

CREATE TABLE IF NOT EXISTS notifications (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid        NOT NULL,
  user_id    uuid        NULL,
  type       text        NOT NULL,
  title      text        NOT NULL,
  body       text        NOT NULL DEFAULT '',
  link       text        NULL,
  data       jsonb       NOT NULL DEFAULT '{}',
  read_at    timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
CREATE POLICY notifications_isolation ON notifications
  USING     (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE INDEX IF NOT EXISTS notifications_inbox ON notifications (org_id, created_at DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON notifications TO npo_app;
