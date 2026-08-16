CREATE TABLE IF NOT EXISTS memory_entries (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('brand_voice','banned_topic','content_pillar','cta_pref','hashtag_pref','style_rule','fact')),
  key        text,
  value      jsonb NOT NULL DEFAULT '{}'::jsonb,
  source     text NOT NULL DEFAULT 'manual' CHECK (source IN ('user_correction','research','manual','inferred')),
  confidence real,
  active     boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid
);
CREATE INDEX IF NOT EXISTS memory_org_kind_idx ON memory_entries(org_id, kind) WHERE active;

CREATE TABLE IF NOT EXISTS posts (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL,
  idea_group uuid,
  title      text NOT NULL,
  brief      text,
  status     text NOT NULL DEFAULT 'suggested'
             CHECK (status IN ('suggested','drafting','drafted','approved','scheduled','posted','archived')),
  platform   text,
  content    text,
  sources    jsonb NOT NULL DEFAULT '[]'::jsonb,
  image_id   uuid,
  origin     text NOT NULL DEFAULT 'agent_suggested' CHECK (origin IN ('agent_suggested','user_requested')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  posted_at  timestamptz
);
CREATE INDEX IF NOT EXISTS posts_org_status_idx ON posts(org_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS org_profile (
  org_id     uuid PRIMARY KEY,
  mission    text,
  one_liner  text,
  audience   text,
  regions    text[] NOT NULL DEFAULT '{}',
  sources    jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS programs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL,
  name        text NOT NULL,
  description text,
  source_url  text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS programs_org_idx ON programs(org_id);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['memory_entries','posts','org_profile','programs'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($f$CREATE POLICY %1$s_isolation ON %1$I
        USING (org_id = current_setting('app.org', true)::uuid)
        WITH CHECK (org_id = current_setting('app.org', true)::uuid)$f$, t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON memory_entries, posts, org_profile, programs TO npo_app;
