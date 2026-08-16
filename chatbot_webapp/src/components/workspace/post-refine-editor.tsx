'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Sparkles, Check, X, RotateCcw, Undo2, Wand2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useRefinePost, useUpdateCampaignPost, useUndoPost, useInvalidatePost } from '@/hooks/use-studio'

/** Fixed baseline chips, always offered after the post's tailored suggestions. */
const BASELINE_INTENTS = ['Shorter', 'Fix typos'] as const

interface RefineProposal { intent: string; caption: string }

/**
 * Tailored refine chips → propose → before/after diff → Apply / Try again / Cancel, plus a
 * server-persisted Undo after Apply. Reusable from the campaign post card and (later) the
 * calendar popover. Stateless about the post's own caption editing — it only proposes/applies.
 */
export function PostRefineEditor({
  campaignId, postId, currentCaption, suggestions = [], className, onApplied, onReverted,
}: {
  campaignId: string
  postId: string
  currentCaption: string
  suggestions?: string[]
  className?: string
  /** Called with the applied caption so an owning editor can keep its textarea in sync. */
  onApplied?: (caption: string) => void
  /** Called with the restored caption after a successful Undo. */
  onReverted?: (caption: string) => void
}) {
  const refine = useRefinePost()
  const applyWrite = useUpdateCampaignPost()
  const undo = useUndoPost()
  const invalidate = useInvalidatePost()

  const [customOpen, setCustomOpen] = useState(false)
  const [customText, setCustomText] = useState('')
  const [proposal, setProposal] = useState<RefineProposal | null>(null)
  // The caption as it was *before* the last Apply — so Undo's affordance can stay visible
  // (the actual restore is server-persisted; this is just to show the control + a hint).
  const [undoable, setUndoable] = useState(false)

  // De-dupe: a tailored chip equal (case-insensitively) to a baseline isn't shown twice.
  const baselineLower = BASELINE_INTENTS.map((b) => b.toLowerCase())
  const tailored = suggestions.filter((s) => s && !baselineLower.includes(s.trim().toLowerCase()))
  const chips = [...new Set([...tailored.map((s) => s.trim()), ...BASELINE_INTENTS])]

  const runRefine = async (intent: string) => {
    const trimmed = intent.trim()
    if (!trimmed) return
    try {
      const res = await refine.mutateAsync({ campaignId, postId, intent: trimmed })
      setProposal({ intent: trimmed, caption: res.caption })
      setUndoable(false)   // a fresh proposal supersedes any prior Apply's undo hint
    } catch { toast.error('Could not refine just now — please try again') }
  }

  const onApply = async () => {
    if (!proposal) return
    try {
      await applyWrite.mutateAsync({ id: postId, content: proposal.caption })
      invalidate(campaignId)
      onApplied?.(proposal.caption)
      setProposal(null)
      setCustomOpen(false)
      setCustomText('')
      setUndoable(true)
      toast.success('Refined caption applied')
    } catch { toast.error('Could not apply — please try again') }
  }

  const onUndo = async () => {
    try {
      const res = await undo.mutateAsync({ campaignId, postId })
      onReverted?.(res.caption)
      setUndoable(false)
      toast.success('Reverted to the previous caption')
    } catch { toast.error('Nothing to undo') }
  }

  const onCancel = () => { setProposal(null); setCustomOpen(false); setCustomText('') }

  const refining = refine.isPending
  const applying = applyWrite.isPending

  return (
    <div className={cn('space-y-2.5', className)}>
      {/* Chip row — hidden while a proposal is being reviewed to keep the diff focused. */}
      {!proposal && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <Sparkles className="h-3 w-3 text-primary" /> Refine
          </span>
          {chips.map((chip) => (
            <button
              key={chip}
              onClick={() => runRefine(chip)}
              disabled={refining}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border border-border bg-background/60 px-2.5 py-0.5 text-xs font-medium text-foreground/80 transition-colors',
                'hover:border-primary/50 hover:bg-primary/10 hover:text-primary disabled:opacity-50',
              )}
            >
              {chip}
            </button>
          ))}
          <button
            onClick={() => setCustomOpen((v) => !v)}
            disabled={refining}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border border-dashed border-border bg-background/60 px-2.5 py-0.5 text-xs font-medium text-muted-foreground transition-colors',
              'hover:border-primary/50 hover:text-primary disabled:opacity-50',
              customOpen && 'border-primary/50 text-primary',
            )}
          >
            <Wand2 className="h-3 w-3" /> Custom…
          </button>
          {refining && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />}
        </div>
      )}

      {/* Custom one-line intent input. */}
      {customOpen && !proposal && (
        <form
          onSubmit={(e) => { e.preventDefault(); runRefine(customText) }}
          className="flex items-center gap-2"
        >
          <input
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            autoFocus
            placeholder="e.g. warmer tone, add a clear call-to-action…"
            disabled={refining}
            className="min-w-0 flex-1 rounded-lg border border-input bg-background/60 px-3 py-1.5 text-sm focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30 disabled:opacity-60"
          />
          <Button type="submit" size="sm" disabled={refining || !customText.trim()}>
            {refining ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Refine
          </Button>
        </form>
      )}

      {/* Before → after diff preview + Apply / Try again / Cancel. */}
      {proposal && (
        <div className="space-y-3 rounded-xl border border-primary/25 bg-primary/[0.04] p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
            <Sparkles className="h-3 w-3" /> Proposed · {proposal.intent}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Before</span>
              <p className="rounded-lg border border-border/60 bg-muted/20 px-2.5 py-2 text-sm leading-relaxed text-muted-foreground line-through decoration-muted-foreground/40">
                {currentCaption || <span className="italic no-underline">No caption</span>}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-sage">After</span>
              <p className="rounded-lg border border-sage/30 bg-sage/[0.08] px-2.5 py-2 text-sm leading-relaxed text-foreground/90">
                {proposal.caption}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={onApply} disabled={applying || refining}>
              {applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Apply
            </Button>
            <Button size="sm" variant="outline" onClick={() => runRefine(proposal.intent)} disabled={refining || applying}>
              {refining ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Try again
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel} disabled={applying}>
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Server-persisted Undo, available after an Apply. Stays until used (don't disable on re-render). */}
      {undoable && !proposal && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Check className="h-3.5 w-3.5 text-sage" />
          <span>Caption updated.</span>
          <button
            onClick={onUndo}
            disabled={undo.isPending}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline disabled:opacity-60"
          >
            {undo.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Undo2 className="h-3 w-3" />} Undo
          </button>
        </div>
      )}
    </div>
  )
}
