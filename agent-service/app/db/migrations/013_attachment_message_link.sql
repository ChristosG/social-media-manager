-- Link uploaded attachments to the message they were sent with, so the chat can show
-- which file(s) a message carried (chips + preview). Attachments are uploaded standalone
-- (before the message exists), then linked when the user sends — hence nullable + set later.
-- ON DELETE CASCADE: deleting a message (or its conversation) drops its attachments too.
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS message_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'attachments_message_id_fkey' AND table_name = 'attachments'
  ) THEN
    EXECUTE 'ALTER TABLE attachments
             ADD CONSTRAINT attachments_message_id_fkey
             FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS attachments_message_id_idx
  ON attachments(message_id) WHERE message_id IS NOT NULL;
