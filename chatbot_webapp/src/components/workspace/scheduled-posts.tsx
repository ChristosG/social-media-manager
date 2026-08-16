'use client'

import { Facebook, Instagram, Clock, Trash2, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useScheduled, useCancelScheduled } from '@/hooks/use-publishing'
import type { ScheduledPost } from '@/lib/studio-api'

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                    */
/* -------------------------------------------------------------------------- */

type BadgeVariant = 'coral' | 'amber' | 'success' | 'muted' | 'outline' | 'destructive'

const STATUS_META: Record<
  ScheduledPost['status'],
  { label: string; variant: BadgeVariant }
> = {
  pending: { label: 'Scheduled', variant: 'amber' },
  publishing: { label: 'Publishing…', variant: 'muted' },
  published: { label: 'Published', variant: 'success' },
  failed: { label: 'Failed', variant: 'destructive' },
  canceled: { label: 'Canceled', variant: 'muted' },
}

const PLATFORM_ICONS: Record<string, React.ElementType> = {
  facebook: Facebook,
  instagram: Instagram,
}

function relativeDate(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = then - Date.now() // positive = future
  const absDiff = Math.abs(diff)
  const m = Math.round(absDiff / 60_000)
  if (m < 1) return 'now'
  if (m < 60) return diff > 0 ? `in ${m}m` : `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return diff > 0 ? `in ${h}h` : `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 7) return diff > 0 ? `in ${d}d` : `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function firstPermalink(result: ScheduledPost['result']): string | null {
  for (const v of Object.values(result)) {
    if (v?.permalink) return v.permalink
  }
  return null
}

/* -------------------------------------------------------------------------- */
/*  Single item card                                                           */
/* -------------------------------------------------------------------------- */

function ScheduledItem({ item }: { item: ScheduledPost }) {
  const cancel = useCancelScheduled()
  const meta = STATUS_META[item.status]
  const permalink = item.status === 'published' ? firstPermalink(item.result) : null
  const isPending = item.status === 'pending'

  const handleCancel = async () => {
    try {
      await cancel.mutateAsync(item.id)
      toast.success('Post canceled')
    } catch {
      toast.error('Could not cancel post')
    }
  }

  return (
    <Card
      className={cn(
        'transition-all',
        item.status === 'canceled' && 'opacity-50',
        item.status !== 'canceled' &&
          'hover:border-primary/30 hover:shadow-[0_6px_20px_-8px_var(--pau-glow-primary)]',
      )}
    >
      <CardContent className="flex items-start gap-3 p-4">
        {/* Platform icons */}
        <div className="mt-0.5 flex shrink-0 gap-1">
          {item.targets.map((t) => {
            const Icon = PLATFORM_ICONS[t.provider]
            return Icon ? (
              <Icon key={t.connection_id} className="h-4 w-4 text-muted-foreground" />
            ) : null
          })}
          {item.targets.length === 0 && (
            <Clock className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {/* Body */}
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="line-clamp-2 text-sm leading-relaxed text-foreground/90">
            {item.caption}
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={meta.variant}>{meta.label}</Badge>

            {isPending && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                {relativeDate(item.scheduled_at)}
              </span>
            )}

            {item.status === 'published' && permalink && (
              <a
                href={permalink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                View post
              </a>
            )}

            {!isPending && item.status !== 'published' && (
              <span className="text-xs text-muted-foreground">
                {relativeDate(item.scheduled_at)}
              </span>
            )}
          </div>
        </div>

        {/* Cancel button */}
        {isPending && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleCancel}
            disabled={cancel.isPending}
            aria-label="Cancel post"
            className="shrink-0 text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/*  Public component                                                           */
/* -------------------------------------------------------------------------- */

export function ScheduledPosts() {
  const { data, isLoading } = useScheduled()

  // Newest first (by scheduled_at)
  const items = [...(data?.items ?? [])].sort(
    (a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime(),
  )

  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
          Scheduled &amp; recent
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Posts you've queued or recently published via Studio.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-xl border border-border bg-card"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-12 text-center">
          <p className="text-sm text-muted-foreground">
            Nothing scheduled — post something from the{' '}
            <strong className="text-foreground/70">Posts</strong> tab.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <ScheduledItem key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}
