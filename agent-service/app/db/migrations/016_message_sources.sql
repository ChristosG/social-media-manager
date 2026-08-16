-- Per-message source citations. When a turn is grounded (the org's own posts, ingested
-- news/web sources, or a live web search), the sources the assistant actually used are
-- captured and stored here so the UI can render click-through provenance chips — and so a
-- later "where did that come from?" can still answer after the conversation is reloaded.
-- Shape: [{"title": str, "url": str, "kind": "web"|"facebook"|"instagram"|..., "snippet": str}]
ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources jsonb NOT NULL DEFAULT '[]'::jsonb;
