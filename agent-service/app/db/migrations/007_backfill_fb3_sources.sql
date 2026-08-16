-- Backfill FB3 custom URL research_source capability rows into first-class `sources`.
-- Why a separate migration with FORCE toggling: both `capabilities` and `sources` are FORCE-RLS, and
-- migrations run as npo_owner with NO app.org set. Under FORCE RLS the owner is still bound by the
-- policies, so a plain INSERT…SELECT (as attempted in 006) is a silent no-op — the SELECT can't see
-- org-scoped capabilities rows and the sources WITH CHECK rejects them. npo_owner has no BYPASSRLS, so
-- we temporarily lift FORCE on both tables (owner-only bypass), copy, then restore. migrate.py wraps
-- each file in one transaction, so this is atomic and ends with FORCE re-enabled.
ALTER TABLE capabilities NO FORCE ROW LEVEL SECURITY;
ALTER TABLE sources      NO FORCE ROW LEVEL SECURITY;

INSERT INTO sources (org_id, kind, name, config)
SELECT org_id, 'web', name,
       jsonb_build_object('url', config->>'url', 'type', 'auto', 'latest_n', 15)
FROM capabilities
WHERE kind = 'research_source' AND org_id IS NOT NULL AND (config->>'url') IS NOT NULL
ON CONFLICT DO NOTHING;

ALTER TABLE capabilities FORCE ROW LEVEL SECURITY;
ALTER TABLE sources      FORCE ROW LEVEL SECURITY;
