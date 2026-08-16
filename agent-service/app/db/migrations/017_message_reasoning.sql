-- The model's thinking trace and the auto-router's reason are shown in the chat UI but were only ever
-- held client-side, so they vanished when the conversation was reloaded or navigated away from. Persist
-- them on the message so the thinking block + "Thought this through · …" hint survive a refresh.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS reasoning    text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS route_reason text;
