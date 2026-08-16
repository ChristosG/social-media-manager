-- 029_post_pillar.sql — tag each post with a content pillar (programs/fundraising/stories/community/…)
-- so insights can show the content mix. No new policy: `posts` is already FORCE row-level-secured.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS pillar text;
