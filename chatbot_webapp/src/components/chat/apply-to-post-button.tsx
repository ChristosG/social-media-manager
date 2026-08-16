'use client'

import { useState } from 'react'
import { Check, Loader2, WandSparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { extractPost } from '@/components/publish/extract-post'
import { useUpdateCampaignPost, useInvalidatePost } from '@/hooks/use-studio'

interface ApplyToPostButtonProps {
  /** The campaign post this refine turn was bound to ("Refine in chat"). */
  postContext: { post_id: string; campaign_id?: string }
  /** The assistant message's markdown — refine_campaign_post bakes the proposed caption into it (fallback). */
  markdown: string
  /** The EXACT proposed caption from the `refine_proposal` event. Preferred over parsing `markdown`, because
   *  the 9B paraphrases the tool reply (dropping the lead-in the parser keys off) → the button used to vanish. */
  proposedCaption?: string
}

/**
 * "Apply to post" — shown under an assistant message whose turn was bound to a campaign post AND that
 * proposed a refined caption. The backend has no separate draft-caption field for the refine flow: the
 * caption is the assistant message's text. We strip the tool's lead-in line and any image markdown to
 * recover just the caption, then write it back via the existing campaign-post update (which already
 * invalidates the campaign + calendar). Returns null when there's no caption worth applying.
 */
export function ApplyToPostButton({ postContext, markdown, proposedCaption: structured }: ApplyToPostButtonProps) {
  const update = useUpdateCampaignPost()
  const invalidate = useInvalidatePost()
  const [applied, setApplied] = useState(false)

  // Prefer the exact caption handed over by the backend; only fall back to scraping the message prose.
  const proposed = (structured?.trim()) || proposedCaption(markdown)
  if (!proposed) return null

  const handleApply = async () => {
    if (applied || update.isPending) return
    try {
      await update.mutateAsync({ id: postContext.post_id, content: proposed })
      if (postContext.campaign_id) invalidate(postContext.campaign_id)
      setApplied(true)
    } catch {
      /* leave the button enabled so the user can retry */
    }
  }

  return (
    <button
      type="button"
      onClick={handleApply}
      disabled={applied || update.isPending}
      aria-label="Apply this refined caption to the campaign post"
      className={cn(
        'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors',
        applied
          ? 'border-sage/30 bg-sage/12 text-sage cursor-default'
          : 'border-sage/40 bg-sage/10 text-sage hover:bg-sage/15 disabled:opacity-60',
      )}
    >
      {applied ? (
        <><Check className="h-3.5 w-3.5" /> Applied</>
      ) : update.isPending ? (
        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Applying…</>
      ) : (
        <><WandSparkles className="h-3.5 w-3.5" /> Apply to post</>
      )}
    </button>
  )
}

/** The tool's lead-in line, stripped so only the caption remains. Matches refine_campaign_post's reply. */
const LEAD_IN = /here is a refined version[^\n]*:?\s*/i

/** Recover the proposed caption from the assistant message: drop image markdown, then the lead-in line.
 * Returns '' unless the tool's lead-in is actually present — so the tool's guard/error replies ("I couldn't
 * refine that…", "Open a campaign post first…") are NOT treated as captions and never become applyable. */
function proposedCaption(markdown: string): string {
  const { caption } = extractPost(markdown)
  if (!LEAD_IN.test(caption)) return ''
  return caption.replace(LEAD_IN, '').trim()
}
