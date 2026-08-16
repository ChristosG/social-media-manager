'use client'

import { useRouter } from 'next/navigation'
import { ExternalLink, Eye, Zap, MousePointerClick, MessageSquarePlus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { usePostInsights } from '@/hooks/use-studio'
import type { InsightsTopPost } from '@/lib/studio-api'
import { TrendChart, type TrendDatum } from './trend-chart'

/* -------------------------------------------------------------------------- */
/*  Top-post drill-down dialog                                                 */
/*                                                                             */
/*  Shows a post's headline metrics + a small growth chart (reach over the     */
/*  captured snapshots), an "Open post" link when a permalink exists, and a    */
/*  "Refine a follow-up" action that seeds the chat composer.                  */
/* -------------------------------------------------------------------------- */

function Stat({ Icon, label, value }: { Icon: React.ElementType; label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-card/60 px-3 py-2.5">
      <span className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </span>
      <span className="text-lg font-bold leading-none tabular-nums text-foreground">
        {value.toLocaleString()}
      </span>
    </div>
  )
}

export function TopPostDialog({
  post,
  open,
  onOpenChange,
}: {
  post: InsightsTopPost | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const { data: history, isLoading } = usePostInsights(open ? post?.post_id ?? null : null)

  const refineFollowUp = () => {
    // We can't cheaply tell whether this post is campaign-linked from the insights
    // payload, so this seeds a generic compose + navigates to /chat (no post-context binding).
    try {
      const caption = (post?.caption ?? '').trim()
      sessionStorage.setItem(
        'pending-compose',
        caption
          ? `Write a follow-up to this post: ${caption}`
          : 'Write a follow-up to this post.',
      )
    } catch {
      /* ignore */
    }
    router.push('/chat')
  }

  const chartData: TrendDatum[] = (history ?? []).map((p) => ({
    label: new Date(p.captured_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    reach: p.reach,
    engagement: p.engagement,
  }))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="pr-6">Top post</DialogTitle>
          <DialogDescription className={cn('line-clamp-3 whitespace-pre-wrap', !post?.caption && 'italic')}>
            {post?.caption || 'No caption'}
          </DialogDescription>
        </DialogHeader>

        {post && (
          <>
            <div className="grid grid-cols-3 gap-2">
              <Stat Icon={Eye} label="Reach" value={post.reach} />
              <Stat Icon={Zap} label="Engagement" value={post.engagement} />
              <Stat Icon={MousePointerClick} label="Link clicks" value={post.link_clicks} />
            </div>

            {/* 7-day growth */}
            <div className="rounded-xl border border-border bg-card/40 px-3 py-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">Growth since published</p>
              {isLoading ? (
                <div className="h-[140px] animate-pulse rounded-lg bg-muted/30" />
              ) : chartData.length >= 2 ? (
                <TrendChart data={chartData} height={140} />
              ) : (
                <p className="py-8 text-center text-xs text-muted-foreground">
                  Not enough data yet — the growth chart fills in over the days after a post.
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              {post.permalink && (
                <Button asChild variant="outline" size="sm">
                  <a href={post.permalink} target="_blank" rel="noopener noreferrer">
                    Open post
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </Button>
              )}
              <Button size="sm" onClick={refineFollowUp}>
                <MessageSquarePlus className="h-3.5 w-3.5" />
                Refine a follow-up
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
