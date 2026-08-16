-- Stop the idle LLM re-classification burn.
--
-- The auto-reply pass (_auto_post_open) used to re-run the conservative LLM safety classifier over the
-- ENTIRE open-comment backlog on EVERY poll. A static backlog of comments the classifier always rates
-- unsafe (complaints, "how can I contact you?", "send me this post", …) therefore cost one LLM call each,
-- every ~10 minutes, forever — even with zero user activity. With ~15 such drafts that is ~15 vLLM
-- chat-completions per poll, around the clock, indefinitely.
--
-- auto_eval_at records that a comment's drafted reply has already been through the auto-post safety gate
-- (safe -> posted, or unsafe/banned -> left as a human-review draft). The pass now only classifies
-- comments where auto_eval_at IS NULL, so each comment is classified at most ONCE.
ALTER TABLE comments ADD COLUMN IF NOT EXISTS auto_eval_at timestamptz;

-- Hot path for the auto-post pass: "open comments with a draft not yet auto-evaluated".
CREATE INDEX IF NOT EXISTS comments_auto_eval_pending
  ON comments (org_id)
  WHERE status = 'open' AND auto_eval_at IS NULL;

-- Backfill: any comment that already carries a drafted/posted reply has effectively been evaluated (the
-- existing backlog has been re-classified hundreds of times). Stamp them so the burn stops on deploy
-- without even one more classification pass.
--
-- The NO FORCE / FORCE wrapper is REQUIRED, not decorative. Migrations run as npo_owner, which OWNS this
-- table, and `comments` is FORCE ROW LEVEL SECURITY — so the tenant policy
-- (org_id = current_setting('app.org', true)::uuid) applies to the owner too. No migration sets app.org,
-- so the predicate is `org_id = NULL` → never true → the UPDATE below matches ZERO rows and Postgres
-- raises NO error. Without this wrapper the backfill is a silent no-op that still records as applied.
-- (DDL above is unaffected — row policies gate DML only.)
--
-- Safe: migrate.py wraps each file in one transaction, and ALTER TABLE takes ACCESS EXCLUSIVE, so no
-- other session can read `comments` during the window in which FORCE is lifted.
ALTER TABLE comments NO FORCE ROW LEVEL SECURITY;
UPDATE comments SET auto_eval_at = now() WHERE auto_eval_at IS NULL AND reply_text <> '';
ALTER TABLE comments FORCE ROW LEVEL SECURITY;
