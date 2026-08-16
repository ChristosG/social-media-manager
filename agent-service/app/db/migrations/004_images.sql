-- FB2: generated images (FLUX). Canonical bytes live here; posts.image_id (already
-- present from 002) can reference a row. Per-org RLS like every other table.
CREATE TABLE IF NOT EXISTS images (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL,
  prompt          text NOT NULL,
  enhanced_prompt text,
  seed            bigint,
  width           integer NOT NULL,
  height          integer NOT NULL,
  steps           integer NOT NULL,
  cfg             real NOT NULL,
  sampler_name    text,
  format          text NOT NULL DEFAULT 'png',
  data            bytea NOT NULL,
  platform        text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid
);
CREATE INDEX IF NOT EXISTS images_org_idx ON images(org_id, created_at DESC);

DO $$
BEGIN
  EXECUTE 'ALTER TABLE images ENABLE ROW LEVEL SECURITY';
  EXECUTE 'ALTER TABLE images FORCE ROW LEVEL SECURITY';
  EXECUTE 'DROP POLICY IF EXISTS images_isolation ON images';
  EXECUTE $f$CREATE POLICY images_isolation ON images
      USING (org_id = current_setting('app.org', true)::uuid)
      WITH CHECK (org_id = current_setting('app.org', true)::uuid)$f$;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON images TO npo_app;
