-- Quarantine flag for durable memory the assistant tried to learn during a turn that consumed
-- attacker-influenceable external content (web search / RAG over ingested web pages). Such entries are
-- NOT injected into prompts until a human approves them in Studio → Knowledge, so a prompt-injection in
-- a scraped page can't silently poison the org's brand voice / banned topics across every future turn.
-- Defaults false, so all existing memory stays active and the normal (no-research) correction path is
-- unaffected.
ALTER TABLE memory_entries ADD COLUMN IF NOT EXISTS pending_review boolean NOT NULL DEFAULT false;

-- The hot prompt-build read filters active AND NOT pending_review; index that exact predicate.
CREATE INDEX IF NOT EXISTS memory_org_kind_approved_idx
  ON memory_entries(org_id, kind) WHERE active AND NOT pending_review;
