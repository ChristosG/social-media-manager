'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Megaphone, Rocket, Trash2, Calendar, Loader2, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { cn } from '@/lib/utils'
import { useCampaigns, useApproveCampaign, useDeleteCampaign } from '@/hooks/use-studio'
import type { Campaign } from '@/lib/studio-api'
import { CampaignDetail } from './campaign-detail'

/* -------------------------------------------------------------------------- */

function formatRelative(iso: string) {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const m = Math.round((Date.now() - then) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function CampaignsEmpty() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
      <Megaphone className="mb-3 h-9 w-9 text-muted-foreground/40" />
      <p className="font-display text-base font-semibold tracking-tight text-foreground">No campaigns yet</p>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
        Plan a campaign by telling the assistant in chat, e.g.{' '}
        <span className="italic">&ldquo;plan a 2-week clean-water awareness push for Instagram&rdquo;</span>.
      </p>
      <Button asChild variant="outline" className="mt-5"><Link href="/chat">Go to chat</Link></Button>
    </div>
  )
}

function CampaignsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-[5.5rem] animate-pulse rounded-2xl border border-border bg-card" />
      ))}
    </div>
  )
}

/* ------------------------------ summary card ------------------------------ */

function CampaignSummaryCard({ campaign, onOpen }: { campaign: Campaign; onOpen: (id: string) => void }) {
  const approve = useApproveCampaign()
  const remove = useDeleteCampaign()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const isProposed = campaign.status === 'proposed'
  const slotCount = campaign.slots.length
  const draftedCount = campaign.slots.filter((s) => s.post_id !== null).length
  const open = () => onOpen(campaign.id)

  const handleApprove = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const res = await approve.mutateAsync(campaign.id)
      open()   // jump into the detail view to watch drafting
      if (res.status === 'done') toast.success(res.message || 'Every post is already drafted')
      else toast.success('Drafting your campaign — opening it so you can watch')
    } catch { toast.error('Could not start drafting — please try again') }
  }

  const handleDelete = async () => {
    try { await remove.mutateAsync(campaign.id); toast.success('Campaign archived') }
    catch { toast.error('Could not archive campaign') }
    finally { setConfirmOpen(false) }
  }

  return (
    <>
      <Card role="button" tabIndex={0} onClick={open}
        onKeyDown={(e) => { if (e.key === 'Enter') open() }}
        className="cursor-pointer transition-all hover:border-primary/40 hover:bg-panel-raised">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={isProposed ? 'amber' : 'success'} className="capitalize">{campaign.status}</Badge>
                {campaign.platform && <Badge variant="outline" className="capitalize">{campaign.platform}</Badge>}
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />{slotCount} slot{slotCount !== 1 ? 's' : ''}
                  {draftedCount > 0 && <span className="text-sage">&nbsp;· {draftedCount} drafted</span>}
                </span>
                <span className="text-xs text-muted-foreground">{formatRelative(campaign.created_at)}</span>
              </div>
              <p className="line-clamp-2 text-sm leading-relaxed text-foreground/90">{campaign.brief}</p>
              {/* progress bar */}
              {slotCount > 0 && (
                <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-sage/70 transition-[width]"
                    style={{ width: `${Math.round((draftedCount / slotCount) * 100)}%` }} />
                </div>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {isProposed && (
                <Button size="sm" onClick={handleApprove} disabled={approve.isPending} className="gap-1.5">
                  {approve.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />}
                  Draft
                </Button>
              )}
              <Button variant="ghost" size="icon-sm" aria-label="Archive campaign"
                className="text-muted-foreground hover:text-destructive"
                onClick={(e) => { e.stopPropagation(); setConfirmOpen(true) }} disabled={remove.isPending}>
                <Trash2 className="h-4 w-4" />
              </Button>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/60" />
            </div>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        title="Archive campaign?"
        description={`"${campaign.brief.slice(0, 80)}${campaign.brief.length > 80 ? '…' : ''}" will be archived and hidden from this list.`}
        confirmLabel="Archive" destructive
        onConfirm={handleDelete} onCancel={() => setConfirmOpen(false)}
      />
    </>
  )
}

/* -------------------------------- panel ---------------------------------- */

export function CampaignsPanel() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { data, isLoading } = useCampaigns()
  const campaigns = (data?.campaigns ?? []).filter((c) => c.status !== 'archived')

  // The focused campaign is driven by component STATE (so a click renders the detail instantly) and mirrored
  // to the `?c=` URL for deep-links / the back button. A same-route query-only router.push isn't reliably
  // reactive in the App Router, so we never depend on the URL alone to switch the view.
  const urlFocus = searchParams.get('c')
  const [focusId, setFocusId] = useState<string | null>(urlFocus)
  useEffect(() => { setFocusId(urlFocus) }, [urlFocus])

  const openCampaign = (id: string) => { setFocusId(id); router.push(`/workspace?tab=campaigns&c=${id}`) }
  const closeCampaign = () => { setFocusId(null); router.push('/workspace?tab=campaigns') }

  if (focusId) return <CampaignDetail id={focusId} onBack={closeCampaign} />

  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">Campaigns</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Multi-post campaigns planned by the assistant — open one to draft, edit, schedule and track each post.
        </p>
      </div>

      {isLoading ? (
        <CampaignsSkeleton />
      ) : campaigns.length === 0 ? (
        <CampaignsEmpty />
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => <CampaignSummaryCard key={c.id} campaign={c} onOpen={openCampaign} />)}
        </div>
      )}
    </section>
  )
}
