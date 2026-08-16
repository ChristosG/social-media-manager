'use client'

import { useState } from 'react'
import { Share2 } from 'lucide-react'
import { extractPost } from './extract-post'
import { PublishPreviewDialog } from './publish-preview-dialog'
import { useConversationDraft } from '@/hooks/use-publishing'

interface PostToSocialsChipProps {
  markdown: string
  postId?: string | null
  conversationId?: string | null
}

/**
 * Renders a subtle "Post to socials" chip below an assistant message.
 * Prefers the clean structured draft (caption from draft_post + latest generated images)
 * when present; falls back to parsing this message's markdown for text-only posts or
 * before any draft exists.
 * Returns null when there is no post-worthy content (no caption and no images).
 */
export function PostToSocialsChip({ markdown, postId, conversationId }: PostToSocialsChipProps) {
  const [open, setOpen] = useState(false)
  const { data } = useConversationDraft(conversationId || undefined)
  const draft = data?.draft

  const fromMarkdown = extractPost(markdown)
  // "Post to socials" publishes the CONVERSATION's current post: the latest caption written by draft_post
  // and ALL images generated in the conversation (both tracked in the structured conversation draft, which
  // is refetched after every turn). We only fall back to parsing this message's markdown when there is no
  // structured draft yet (e.g. a plain text-only post the user typed) — never preferring it over the draft,
  // since a non-caption message (like "what image do you want?") would otherwise become a bogus caption.
  const caption = draft?.caption || fromMarkdown.caption
  const images = draft && draft.images.length > 0 ? draft.images : fromMarkdown.images

  // Only show the chip when there is something worth publishing
  if (!caption && images.length === 0) return null

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
        aria-label="Post to socials"
      >
        <Share2 className="h-3.5 w-3.5" />
        Post to socials
      </button>
      <PublishPreviewDialog
        open={open}
        onOpenChange={setOpen}
        initialCaption={caption}
        initialImages={images}
        postId={postId}
      />
    </>
  )
}
