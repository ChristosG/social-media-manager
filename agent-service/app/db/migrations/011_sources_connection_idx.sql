-- Index the auto-ingest hot path: get_source_by_connection looks up sources by connection_id on
-- every connect / reconnect / add-source. Partial index (non-null) keeps it lean. Idempotent.
CREATE INDEX IF NOT EXISTS sources_connection_id_idx ON sources(connection_id) WHERE connection_id IS NOT NULL;
