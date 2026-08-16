-- Phase 2 social connectors: one OAuth credential + connected identity per (org, provider, external_id).
-- access_token_enc is AES-GCM ciphertext (nonce||ct||tag) — NEVER stored or logged in plaintext.
CREATE TABLE IF NOT EXISTS connections (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL,
  provider         text NOT NULL CHECK (provider IN ('facebook','instagram')),
  external_id      text NOT NULL,
  display_name     text,
  access_token_enc bytea NOT NULL,
  token_expires_at timestamptz,
  scopes           text,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','needs_reconnect','revoked')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS connections_org_provider_ext_uq ON connections(org_id, provider, external_id);

ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE connections FORCE ROW LEVEL SECURITY;
CREATE POLICY conn_all ON connections USING (org_id = current_setting('app.org', true)::uuid)
                                      WITH CHECK (org_id = current_setting('app.org', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON connections TO npo_app;
