-- Back the campaign lifecycle read: scheduled_posts.latest_for_post filters WHERE post_id=$1
-- ORDER BY created_at DESC. Without this index it is a sequential scan, run once per slot by the
-- (currently 2s-polled) campaign detail enrichment. (DDL-only; safe under FORCE RLS.)
CREATE INDEX IF NOT EXISTS scheduled_posts_org_post_idx ON scheduled_posts(org_id, post_id);
