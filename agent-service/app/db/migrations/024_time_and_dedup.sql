-- WS1 foundations: a real time dimension, async campaign-fill status, and ledger dedup.
-- NOTE: DDL only. Migrations run as npo_owner under FORCE ROW LEVEL SECURITY, so a data UPDATE here would
-- be RLS-filtered to 0 rows (app.org is unset) — every existing migration is DDL-only for this reason.
-- Existing rows therefore keep planned_at = NULL (the calendar falls back to planned_for) and idea_group =
-- NULL (they're simply not covered by the dedup index until next touched); going-forward writes populate both.

-- (1) Time-of-day for planned posts + campaign slots. Same-day posts can finally carry a real time (22:00 vs
-- 22:30). Keep the DATE columns for back-compat + date-range filtering; the timestamp is source of truth when set.
ALTER TABLE posts          ADD COLUMN IF NOT EXISTS planned_at timestamptz;
ALTER TABLE campaign_slots ADD COLUMN IF NOT EXISTS slot_at    timestamptz;

-- (2) Campaign fill now runs in the background (no more 504 timeout-race on approve); the panel polls these.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS fill_status text;   -- NULL | 'filling' | 'done' | 'error'
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS fill_error  text;

-- (3) Ledger dedup: idea_key is a normalized-title slug (TEXT), populated by create_post. (posts.idea_group
-- is a UUID grouping column — not a text key — so we add a dedicated text key.) Enforce at most one LIVE row
-- per idea so re-suggesting / re-drafting the same idea can't duplicate. Existing rows have idea_key NULL
-- (not covered), so the index builds empty and is non-disruptive.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS idea_key text;
CREATE UNIQUE INDEX IF NOT EXISTS posts_idea_key_live_uidx
  ON posts(org_id, idea_key)
  WHERE idea_key IS NOT NULL AND status IN ('suggested','drafting','drafted','approved','scheduled');
