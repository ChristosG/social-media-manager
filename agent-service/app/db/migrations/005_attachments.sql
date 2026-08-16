-- FB4d: user-uploaded files (PDF/text/images). The LLM is text-only, so we extract
-- and store content_text at upload time; the canonical bytes live here too (for download).
-- Per-org RLS like every other table.
CREATE TABLE IF NOT EXISTS attachments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL,
  user_id       uuid,
  filename      text NOT NULL,
  mime_type     text,
  file_size     bigint,
  content_text  text,
  data          bytea,
  status        text NOT NULL DEFAULT 'ready',
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS attachments_org_idx ON attachments(org_id, created_at DESC);

DO $$
BEGIN
  EXECUTE 'ALTER TABLE attachments ENABLE ROW LEVEL SECURITY';
  EXECUTE 'ALTER TABLE attachments FORCE ROW LEVEL SECURITY';
  EXECUTE 'DROP POLICY IF EXISTS attachments_isolation ON attachments';
  EXECUTE $f$CREATE POLICY attachments_isolation ON attachments
      USING (org_id = current_setting('app.org', true)::uuid)
      WITH CHECK (org_id = current_setting('app.org', true)::uuid)$f$;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON attachments TO npo_app;
