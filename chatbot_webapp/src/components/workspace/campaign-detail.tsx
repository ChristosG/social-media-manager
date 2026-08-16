'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft, Rocket, Trash2, Loader2, MessageSquarePlus, Plus, AlertTriangle, RotateCw, Check, Send, PenLine,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import {
  useCampaign, useApproveCampaign, useDeleteCampaign, useApproveAllCampaignPosts, useScheduleApprovedCampaign,
  useAddCustomDraft,
} from '@/hooks/use-studio'
import { CampaignPostCard } from './campaign-post-card'

export function CampaignDetail({ id, onBack }: { id: string; onBack?: () => void }) {
  const router = useRouter()
  const { data, isLoading } = useCampaign(id)
  const approve = useApproveCampaign()
  const approveAll = useApproveAllCampaignPosts()
  const scheduleApproved = useScheduleApprovedCampaign()
  const remove = useDeleteCampaign()
  const addCustom = useAddCustomDraft()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [scheduleConfirmOpen, setScheduleConfirmOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(false)
  const [customCaption, setCustomCaption] = useState('')

  const handleAddCustom = async () => {
    const caption = customCaption.trim()
    if (!caption) return
    try {
      await addCustom.mutateAsync({ campaignId: id, caption })
      toast.success('Custom draft added — refine it, generate an image, or edit below')
      setCustomCaption(''); setCustomOpen(false)
    } catch { toast.error('Could not add the draft — please try again') }
  }

  const back = () => (onBack ? onBack() : router.push('/workspace?tab=campaigns'))

  const c = data?.campaign

  const handleApprove = async () => {
    try {
      const res = await approve.mutateAsync(id)
      if (res.status === 'done') toast.success(res.message || 'Every post is already drafted')
      else toast.success('Drafting your campaign — posts will appear below as they’re written')
    } catch { toast.error('Could not start drafting — please try again') }
  }

  const handleApproveAll = async () => {
    try {
      const res = await approveAll.mutateAsync(id)
      toast.success(res.approved > 0
        ? `Approved ${res.approved} post${res.approved !== 1 ? 's' : ''} — ready to schedule`
        : 'Nothing left to approve')
    } catch { toast.error('Could not approve — please try again') }
  }

  const handleScheduleApproved = async () => {
    try {
      const res = await scheduleApproved.mutateAsync(id)
      const n = res.scheduled
      if (n > 0 && res.skipped.length === 0) toast.success(`Scheduled ${n} post${n !== 1 ? 's' : ''} 🎉`)
      else if (n > 0) toast.success(`Scheduled ${n} · skipped ${res.skipped.length} (${res.skipped[0].reason})`)
      else toast.error(res.skipped[0]?.reason ? `Couldn’t schedule — ${res.skipped[0].reason}` : 'Nothing to schedule')
    } catch { toast.error('Could not schedule — please try again') }
    finally { setScheduleConfirmOpen(false) }
  }

  const handleArchive = async () => {
    try { await remove.mutateAsync(id); toast.success('Campaign archived'); back() }
    catch { toast.error('Could not archive campaign') }
    finally { setConfirmOpen(false) }
  }

  const editInChat = () => {
    try {
      // Bind the chat turn to THIS campaign so the assistant edits the right one (and the landing shows it).
      sessionStorage.setItem('pending-context', JSON.stringify({
        campaignId: id, kind: 'campaign', label: c?.brief || 'this campaign' }))
      sessionStorage.setItem('pending-compose', "What would you like to change? (add a post, move a date, or remove one)")
    } catch { /* ignore */ }
    router.push('/chat')
  }

  const addPostInChat = () => {
    try {
      sessionStorage.setItem('pending-context', JSON.stringify({
        campaignId: id, kind: 'campaign', label: c?.brief || 'this campaign' }))
      sessionStorage.setItem('pending-compose', 'Add a new post to this campaign about: ')
    } catch { /* ignore */ }
    router.push('/chat')
  }

  if (isLoading) {
    return <div className="h-64 animate-pulse rounded-2xl border border-border bg-card" />
  }
  if (!c) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
        <p className="font-display text-base font-semibold text-foreground">This campaign isn’t available</p>
        <p className="mt-1.5 text-sm text-muted-foreground">It may have been archived.</p>
        <Button variant="outline" className="mt-5" onClick={back}><ArrowLeft className="h-4 w-4" /> Back to campaigns</Button>
      </div>
    )
  }

  const isProposed = c.status === 'proposed'
  const filling = c.fill_status === 'filling'
  const slots = c.slots.slice().sort((a, b) => a.position - b.position)
  const filled = slots.filter((s) => s.post).length
  const p = c.progress

  return (
    <section className="space-y-4">
      {/* Header */}
      <div className="space-y-3">
        <button onClick={back} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Campaigns
        </button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={isProposed ? 'amber' : 'success'} className="capitalize">{c.status}</Badge>
              {c.platform && <Badge variant="outline" className="capitalize">{c.platform}</Badge>}
              {p && (
                <span className="text-xs text-muted-foreground">
                  {p.total} post{p.total !== 1 ? 's' : ''}
                  {p.drafted > 0 && <span className="text-sage"> · {p.drafted} drafted</span>}
                  {p.approved > 0 && <span className="text-sage"> · {p.approved} approved</span>}
                  {p.scheduled > 0 && <span className="text-primary"> · {p.scheduled} scheduled</span>}
                  {p.posted > 0 && <span className="text-sage"> · {p.posted} posted</span>}
                  {p.failed > 0 && <span className="text-destructive"> · {p.failed} failed</span>}
                </span>
              )}
            </div>
            <h2 className="font-display text-lg font-semibold leading-snug tracking-tight text-foreground">{c.brief}</h2>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button variant="outline" size="sm" onClick={() => setCustomOpen(true)}>
              <PenLine className="h-3.5 w-3.5" /> Add a custom draft
            </Button>
            <Button variant="outline" size="sm" onClick={addPostInChat}>
              <Plus className="h-3.5 w-3.5" /> Add a post
            </Button>
            <Button variant="outline" size="sm" onClick={editInChat}>
              <MessageSquarePlus className="h-3.5 w-3.5" /> Edit in chat
            </Button>
            <Button variant="ghost" size="icon-sm" aria-label="Archive campaign"
              className="text-muted-foreground hover:text-destructive" onClick={() => setConfirmOpen(true)} disabled={remove.isPending}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Primary CTA — a pure function of the slot rollup, so a PROPOSED campaign never shows a
          drafting spinner and "Draft" is always distinct from "committing". */}
      {filling ? (
        <div className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/8 px-4 py-2.5 text-sm text-primary">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
          Drafting {filled} of {slots.length} posts… they’ll appear below as they’re written.
        </div>
      ) : filled === 0 ? (
        <Button onClick={handleApprove} disabled={approve.isPending} className="gap-1.5">
          {approve.isPending
            ? (<><Loader2 className="h-4 w-4 animate-spin" /> Starting…</>)
            : (<><Rocket className="h-4 w-4" /> Draft all posts</>)}
        </Button>
      ) : filled === slots.length ? (
        // Only prompt to review/approve while there are still DRAFTED (unapproved) posts; once everything is
        // approved/scheduled this banner would be stale (the schedule CTA + per-card states take over).
        p && p.drafted > 0 ? (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-sage/30 bg-sage/8 px-4 py-2.5 text-sm text-sage">
            <Check className="h-4 w-4 shrink-0" />
            <span className="min-w-0 flex-1">
              All {slots.length} post{slots.length !== 1 ? 's' : ''} drafted — review each, then approve to schedule.
            </span>
            <Button size="sm" variant="outline" onClick={handleApproveAll} disabled={approveAll.isPending}>
              {approveAll.isPending
                ? (<><Loader2 className="h-3.5 w-3.5 animate-spin" /> Approving…</>)
                : (<><Check className="h-3.5 w-3.5" /> Approve all {p.drafted}</>)}
            </Button>
          </div>
        ) : null
      ) : (
        <Button onClick={handleApprove} disabled={approve.isPending} className="gap-1.5">
          <Rocket className="h-4 w-4" /> Draft remaining {slots.length - filled} post{slots.length - filled !== 1 ? 's' : ''}
        </Button>
      )}

      {/* Schedule CTA — appears once posts are approved; schedules them at their planned dates in one click */}
      {p && p.approved > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/8 px-4 py-2.5 text-sm text-primary">
          <Send className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1">
            {p.approved} post{p.approved !== 1 ? 's' : ''} approved — schedule {p.approved !== 1 ? 'them' : 'it'} to your accounts at their planned dates.
          </span>
          <Button size="sm" onClick={() => setScheduleConfirmOpen(true)} disabled={scheduleApproved.isPending}>
            {scheduleApproved.isPending
              ? (<><Loader2 className="h-3.5 w-3.5 animate-spin" /> Scheduling…</>)
              : (<><Send className="h-3.5 w-3.5" /> Schedule all approved</>)}
          </Button>
        </div>
      )}

      {/* Error banner */}
      {c.fill_status === 'error' && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-2.5 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1">Drafting hit a snag{c.fill_error ? ` — ${c.fill_error}` : ''}.</span>
          <Button size="sm" variant="outline" onClick={handleApprove} disabled={approve.isPending}>
            <RotateCw className="h-3.5 w-3.5" /> Retry
          </Button>
        </div>
      )}

      {/* Posts */}
      <div className="space-y-2.5">
        {slots.map((slot) => <CampaignPostCard key={slot.id} slot={slot} campaignId={c.id} filling={filling} />)}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Archive campaign?"
        description={`"${c.brief.slice(0, 80)}${c.brief.length > 80 ? '…' : ''}" will be archived and hidden from this list.`}
        confirmLabel="Archive"
        destructive
        onConfirm={handleArchive}
        onCancel={() => setConfirmOpen(false)}
      />

      <ConfirmDialog
        open={scheduleConfirmOpen}
        title="Schedule approved posts?"
        description={`${p?.approved ?? 0} approved post${(p?.approved ?? 0) !== 1 ? 's' : ''} will be queued to your connected account${(p?.approved ?? 0) !== 1 ? 's' : ''} at the date on each card. Posts without a connected account, an image (Instagram), or a future date are skipped.`}
        confirmLabel="Schedule"
        onConfirm={handleScheduleApproved}
        onCancel={() => setScheduleConfirmOpen(false)}
      />

      {/* Add a custom draft — the user writes the caption themselves; it then lands as a normal drafted post
          with every AI feature (image gen + refine chips) available on its card below. */}
      <Dialog open={customOpen} onOpenChange={(o) => { if (!o) { setCustomOpen(false); setCustomCaption('') } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add a custom draft</DialogTitle>
            <DialogDescription>
              Write the caption yourself. Once added, you can generate an image and use the refine chips on its card.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={customCaption}
            onChange={(e) => setCustomCaption(e.target.value)}
            rows={6}
            placeholder="Write your post caption…"
            className="resize-y text-sm leading-relaxed"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => { setCustomOpen(false); setCustomCaption('') }}>Cancel</Button>
            <Button onClick={handleAddCustom} disabled={!customCaption.trim() || addCustom.isPending}>
              {addCustom.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PenLine className="h-4 w-4" />}
              Add draft
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
