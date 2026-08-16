-- The org's primary platform (e.g. "instagram") — set at onboarding and learned from chat ("I only post
-- on Instagram"). The brain/drafter default to it when the user doesn't name a platform, so posts land
-- ready for where they actually publish.
ALTER TABLE org_profile ADD COLUMN IF NOT EXISTS default_platform text;
