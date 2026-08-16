CREATE TABLE IF NOT EXISTS orgs (
  id          uuid PRIMARY KEY,
  name        text NOT NULL,
  website_url text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL,
  user_id    uuid NOT NULL,
  title      text NOT NULL DEFAULT 'New conversation',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL,
  role            text NOT NULL CHECK (role IN ('user','assistant','system')),
  content         text NOT NULL,
  meta            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conv_idx ON messages(conversation_id, created_at);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE messages      FORCE ROW LEVEL SECURITY;

CREATE POLICY conv_isolation ON conversations
  USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE POLICY msg_isolation ON messages
  USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON conversations, messages, orgs TO npo_app;
