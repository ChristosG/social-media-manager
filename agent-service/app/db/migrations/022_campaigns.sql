-- A multi-post campaign: one brief expands into N dated slots, each later drafted into a ledger post.
CREATE TABLE IF NOT EXISTS campaigns (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL,
  brief      text NOT NULL,
  platform   text,
  status     text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS campaign_slots (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL,
  campaign_id uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  slot_date   date NOT NULL,
  angle       text NOT NULL,
  platform    text,
  post_id     uuid REFERENCES posts(id) ON DELETE SET NULL,
  position    int  NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns FORCE ROW LEVEL SECURITY;
ALTER TABLE campaign_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_slots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS campaigns_iso ON campaigns;
CREATE POLICY campaigns_iso ON campaigns USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
DROP POLICY IF EXISTS campaign_slots_iso ON campaign_slots;
CREATE POLICY campaign_slots_iso ON campaign_slots USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON campaigns, campaign_slots TO npo_app;
CREATE INDEX IF NOT EXISTS campaign_slots_campaign_idx ON campaign_slots(org_id, campaign_id, position);
