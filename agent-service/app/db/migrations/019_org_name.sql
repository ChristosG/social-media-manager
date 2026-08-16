-- The org's own NAME, so the assistant refers to it correctly ("BRCAStrong") instead of inventing a
-- placeholder like "[Organization Name]". Set at onboarding, by Research, or in Studio. Distinct from the
-- auth tenant name (which the agent-service doesn't receive) so grounding stays self-contained here.
ALTER TABLE org_profile ADD COLUMN IF NOT EXISTS name text;
