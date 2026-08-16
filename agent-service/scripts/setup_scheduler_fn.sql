-- Run as the `platform` superuser (NOT npo_owner). Installs the scheduler's cross-org due-source reader.
-- SECURITY DEFINER + platform ownership → bypasses RLS within the function ONLY; returns ids only (no
-- content). npo_app may EXECUTE but cannot itself bypass RLS, so FORCE RLS + the npo_owner model stay intact.
CREATE OR REPLACE FUNCTION sched_due_sources(p_limit int)
  RETURNS TABLE(org_id uuid, source_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT org_id, id FROM sources
    WHERE enabled AND cadence = 'daily' AND (next_due_at IS NULL OR next_due_at <= now())
    ORDER BY next_due_at NULLS FIRST
    LIMIT p_limit
  $$;
REVOKE ALL ON FUNCTION sched_due_sources(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sched_due_sources(int) TO npo_app;
