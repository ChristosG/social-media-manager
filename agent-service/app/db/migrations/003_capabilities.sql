-- Capabilities registry: the agent's platforms/content-types/research-sources/skills as DATA.
-- org_id IS NULL = global default (visible to every org). An org row overrides a global of the
-- same (kind,name); an org override with enabled=false disables that global for the org.
CREATE TABLE IF NOT EXISTS capabilities (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid,                         -- NULL = global default
  kind       text NOT NULL CHECK (kind IN ('platform','content_type','research_source','skill_prompt','skill_tool')),
  name       text NOT NULL,
  config     jsonb NOT NULL DEFAULT '{}'::jsonb,
  enabled    boolean NOT NULL DEFAULT true,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS capabilities_global_uq ON capabilities(kind, name) WHERE org_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS capabilities_org_uq    ON capabilities(org_id, kind, name) WHERE org_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS capabilities_kind_idx ON capabilities(kind) WHERE enabled;

-- Seed global defaults BEFORE enabling RLS: npo_owner inserts org_id=NULL rows here; once FORCE RLS
-- is on, even the owner is bound by the WITH CHECK (org_id = app.org), which would reject NULL.
INSERT INTO capabilities(org_id, kind, name, config) VALUES
  (NULL,'platform','linkedin',  '{"label":"LinkedIn","max_chars":3000,"tone":"professional, warm, story-led","hashtags":"2-3 relevant","image":[1200,627]}'),
  (NULL,'platform','instagram', '{"label":"Instagram","max_chars":2200,"tone":"vivid, personal, emoji-friendly","hashtags":"5-10","image":[1080,1080]}'),
  (NULL,'platform','x',         '{"label":"X","max_chars":280,"tone":"punchy, concise","hashtags":"1-2","image":[1600,900]}'),
  (NULL,'platform','facebook',  '{"label":"Facebook","max_chars":2000,"tone":"friendly, community","hashtags":"0-2","image":[1200,630]}'),
  (NULL,'content_type','Story Spotlight',    '{"description":"Highlight one beneficiary and their journey.","structure":"hook -> story -> impact -> call to action"}'),
  (NULL,'content_type','Impact Update',      '{"description":"Share concrete outcomes and numbers.","structure":"headline stat -> context -> thank supporters"}'),
  (NULL,'content_type','Volunteer Shoutout', '{"description":"Thank and feature a volunteer or foster.","structure":"name -> what they did -> invite others"}'),
  (NULL,'content_type','Event Promo',        '{"description":"Promote an upcoming event or drive.","structure":"what/when/where -> why it matters -> RSVP"}'),
  (NULL,'research_source','Tavily Web Search','{"type":"tavily","enabled":true}')
ON CONFLICT DO NOTHING;

ALTER TABLE capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE capabilities FORCE ROW LEVEL SECURITY;
CREATE POLICY cap_select ON capabilities FOR SELECT
  USING (org_id = current_setting('app.org', true)::uuid OR org_id IS NULL);
CREATE POLICY cap_insert ON capabilities FOR INSERT
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE POLICY cap_update ON capabilities FOR UPDATE
  USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
CREATE POLICY cap_delete ON capabilities FOR DELETE
  USING (org_id = current_setting('app.org', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON capabilities TO npo_app;
