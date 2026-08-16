-- Run as the `platform` superuser (NOT npo_owner). Installs the publish scheduler's cross-org due-post reader.
-- SECURITY DEFINER + platform ownership → bypasses RLS within the function ONLY; returns ids only (no
-- content). npo_app may EXECUTE but cannot itself bypass RLS, so FORCE RLS + the npo_owner model stay intact.
CREATE OR REPLACE FUNCTION sched_due_posts(lim int)
  RETURNS TABLE(org_id uuid, scheduled_post_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT org_id, id FROM scheduled_posts
    WHERE status = 'pending' AND scheduled_at <= now()
    ORDER BY scheduled_at
    LIMIT lim
  $$;
REVOKE ALL ON FUNCTION sched_due_posts(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sched_due_posts(int) TO npo_app;

-- Reaper: cross-org reader of posts STUCK in 'publishing' (worker claimed then died). Read-only + ids only,
-- same SECURITY DEFINER model as sched_due_posts. The worker then calls the org-scoped scheduled_posts.reap
-- to requeue/fail each one (so the actual state change stays under RLS + the normal repo path).
CREATE OR REPLACE FUNCTION sched_stale_publishing(timeout_secs int, lim int)
  RETURNS TABLE(org_id uuid, scheduled_post_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT org_id, id FROM scheduled_posts
    WHERE status = 'publishing' AND updated_at < now() - make_interval(secs => timeout_secs)
    ORDER BY updated_at
    LIMIT lim
  $$;
REVOKE ALL ON FUNCTION sched_stale_publishing(int, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sched_stale_publishing(int, int) TO npo_app;

-- Comments worker: cross-org reader of orgs that have a comment-capable (engage) connection. Same
-- SECURITY DEFINER + ids-only model as sched_due_posts. The worker then calls the org-scoped
-- ingest_org_comments (which runs under RLS) for each. FB needs read+manage engagement; IG one scope.
CREATE OR REPLACE FUNCTION engage_capable_orgs(lim int)
  RETURNS TABLE(org_id uuid)
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT DISTINCT org_id FROM connections
    WHERE status = 'active'
      AND ( (provider = 'facebook'
             AND scopes LIKE '%pages_read_engagement%'
             AND scopes LIKE '%pages_manage_engagement%')
         OR (provider = 'instagram'
             AND scopes LIKE '%instagram_manage_comments%') )
    LIMIT lim
  $$;
REVOKE ALL ON FUNCTION engage_capable_orgs(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION engage_capable_orgs(int) TO npo_app;
