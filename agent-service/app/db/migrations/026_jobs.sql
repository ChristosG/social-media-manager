-- Phase 2: one generic durable job queue — the publish-worker pattern (atomic claim + lease + reaper),
-- generalized over a `kind` discriminator. All durable background work (campaign fill, source ingest,
-- comment poll/reply, publish dispatch, memory consolidation) becomes a row here, drained by the worker
-- tier. Transactional enqueue (in the same org_tx as the business write) removes the dual-write gap.
-- DDL only (safe under FORCE RLS). npo_app gets DML via the initdb ALTER DEFAULT PRIVILEGES.
CREATE TABLE IF NOT EXISTS jobs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL,
  kind         text NOT NULL,
  dedup_key    text,
  priority     int  NOT NULL DEFAULT 100,                 -- lower = sooner
  payload      jsonb NOT NULL DEFAULT '{}'::jsonb,
  state        text NOT NULL DEFAULT 'queued',            -- queued | running | succeeded | failed | dead
  attempts     int  NOT NULL DEFAULT 0,
  max_attempts int  NOT NULL DEFAULT 5,
  run_after    timestamptz NOT NULL DEFAULT now(),
  leased_until timestamptz,
  locked_by    text,
  progress     jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_error   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- Enqueue idempotency: at most one LIVE (queued/running) job per (org_id, kind, dedup_key) — so a periodic
-- enqueuer tick run by two replicas can't create duplicates. Scoped by org_id (a dedup_key is per-tenant;
-- two tenants enqueuing the same key must NOT collide).
CREATE UNIQUE INDEX IF NOT EXISTS jobs_dedup_live_uidx ON jobs(org_id, kind, dedup_key)
  WHERE dedup_key IS NOT NULL AND state IN ('queued', 'running');

-- Claim path: due queued jobs, highest priority then oldest run_after.
CREATE INDEX IF NOT EXISTS jobs_due_idx ON jobs(priority, run_after) WHERE state = 'queued';

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS jobs_isolation ON jobs;
CREATE POLICY jobs_isolation ON jobs
  USING (org_id = current_setting('app.org', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org', true)::uuid);
