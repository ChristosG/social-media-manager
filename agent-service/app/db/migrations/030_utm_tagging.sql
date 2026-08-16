-- 030_utm_tagging.sql — opt-in: when on, outbound links in a published caption get utm_* params so the org
-- can attribute social traffic in their own analytics. Off by default (it lengthens public URLs).
ALTER TABLE org_settings ADD COLUMN IF NOT EXISTS utm_tagging boolean NOT NULL DEFAULT false;
