-- Per-org prompt overrides. The assistant ships with sensible default prompt templates
-- (app/agent/prompts.py); a non-engineer can edit them in Studio → Prompts. An override
-- row here replaces the default for that org + key, consumed on the next message. Per-org
-- RLS like every other table.
CREATE TABLE IF NOT EXISTS prompt_overrides (
  org_id     uuid NOT NULL,
  key        text NOT NULL,
  template   text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, key)
);

DO $$
BEGIN
  EXECUTE 'ALTER TABLE prompt_overrides ENABLE ROW LEVEL SECURITY';
  EXECUTE 'ALTER TABLE prompt_overrides FORCE ROW LEVEL SECURITY';
  EXECUTE 'DROP POLICY IF EXISTS prompt_overrides_isolation ON prompt_overrides';
  EXECUTE $f$CREATE POLICY prompt_overrides_isolation ON prompt_overrides
      USING (org_id = current_setting('app.org', true)::uuid)
      WITH CHECK (org_id = current_setting('app.org', true)::uuid)$f$;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON prompt_overrides TO npo_app;
