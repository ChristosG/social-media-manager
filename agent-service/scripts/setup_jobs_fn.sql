-- Run as the `platform` superuser (NOT npo_owner). Cross-org readers for the agent-worker tier.
-- SECURITY DEFINER + platform ownership → bypasses RLS WITHIN the function only; returns ids only (no
-- payload). npo_app may EXECUTE but cannot itself bypass RLS, so FORCE RLS + the npo_owner model stay intact.
-- The worker then calls the org-scoped jobs.claim()/requeue_stale() (under RLS) for each id.

-- Due queued jobs across all orgs, restricted to the kinds this worker can handle, highest priority first.
CREATE OR REPLACE FUNCTION job_due(lim int, kinds text[])
  RETURNS TABLE(org_id uuid, job_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT org_id, id FROM jobs
    WHERE state = 'queued' AND run_after <= now() AND kind = ANY(kinds)
    ORDER BY priority, run_after
    LIMIT lim
  $$;
REVOKE ALL ON FUNCTION job_due(int, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION job_due(int, text[]) TO npo_app;

-- Cross-org reader of jobs STUCK in 'running' past their lease (the worker that claimed them died).
-- Same ids-only model; the worker requeues each via the org-scoped jobs.requeue_stale().
CREATE OR REPLACE FUNCTION job_reap_stale(lim int)
  RETURNS TABLE(org_id uuid, job_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT org_id, id FROM jobs
    WHERE state = 'running' AND leased_until < now()
    ORDER BY leased_until
    LIMIT lim
  $$;
REVOKE ALL ON FUNCTION job_reap_stale(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION job_reap_stale(int) TO npo_app;
