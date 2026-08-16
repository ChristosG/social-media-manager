-- Sticky per-conversation campaign/post binding.
--
-- "Edit in chat" / "Refine in chat" open a fresh conversation dedicated to ONE campaign or post. The first
-- turn carries that binding as post_context; before this, follow-up turns dropped it (the binding lived only
-- in a per-turn ContextVar), so "add another post" / "make it shorter" lost the campaign/post and the agent
-- replied "open a campaign with 'Edit in chat' first". Persisting the binding on the conversation lets EVERY
-- later turn (and a reload) inherit it. No FK: a post/campaign may be archived without orphaning the chat.
ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS active_campaign_id uuid,
  ADD COLUMN IF NOT EXISTS active_post_id     uuid;
