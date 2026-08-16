-- A target calendar date for a ledger idea/draft not yet scheduled to publish. Lets a suggested post
-- sit on a future day on the content calendar before it's drafted/scheduled. Nullable; existing rows
-- unaffected.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS planned_for date;
CREATE INDEX IF NOT EXISTS posts_org_planned_idx ON posts(org_id, planned_for) WHERE planned_for IS NOT NULL;
