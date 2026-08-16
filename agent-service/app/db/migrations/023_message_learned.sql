-- Persist what the assistant LEARNED on a turn (preferences/voice/facts actually written to
-- memory_entries) so the distinct "Learned" chip survives a reload — same idea as messages.reasoning
-- / messages.route_reason. A JSON array of {kind, label, pending}; NULL/[] when nothing was learned.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS learned jsonb;
