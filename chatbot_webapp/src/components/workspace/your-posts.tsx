'use client'

import { useState, useEffect, useRef } from 'react'
import { Facebook, Instagram, Linkedin, ExternalLink, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useSocialPosts, useRefreshSocials } from '@/hooks/use-publishing'

/* -------------------------------------------------------------------------- */
/*  Types + helpers                                                            */
/* -------------------------------------------------------------------------- */

type Platform = 'facebook' | 'instagram' | 'linkedin'

interface PlatformDef {
  id: Platform
  label: string
  Icon: React.ElementType
}

const PLATFORMS: PlatformDef[] = [
  { id: 'facebook', label: 'Facebook', Icon: Facebook },
  { id: 'instagram', label: 'Instagram', Icon: Instagram },
  { id: 'linkedin', label: 'LinkedIn', Icon: Linkedin },
]

function relativeDate(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 2) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/* -------------------------------------------------------------------------- */
/*  Platform switcher                                                          */
/* -------------------------------------------------------------------------- */

function PlatformSwitcher({
  selected,
  onChange,
}: {
  selected: Platform
  onChange: (p: Platform) => void
}) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-1 rounded-xl border border-border bg-panel p-1">
        {PLATFORMS.map(({ id, label, Icon }) => (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <button
                onClick={() => onChange(id)}
                aria-label={label}
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-lg transition-all',
                  selected === id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-panel-raised hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent>{label}</TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  )
}

/* -------------------------------------------------------------------------- */
/*  LinkedIn info state                                                        */
/* -------------------------------------------------------------------------- */

function LinkedInInfoState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-8 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-muted/60">
        <Linkedin className="h-7 w-7 text-muted-foreground" />
      </div>
      <p className="mt-4 font-display text-base font-semibold tracking-tight text-foreground">
        LinkedIn auto-import isn't available
      </p>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        LinkedIn's API is closed to third parties, so we can't pull your posts automatically. To
        reuse a LinkedIn post, paste its URL as a source in{' '}
        <strong className="text-foreground/80">Studio → Sources</strong>.
      </p>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Empty state for a connected platform with no posts                        */
/* -------------------------------------------------------------------------- */

function PlatformEmptyState({ platform, Icon }: { platform: string; Icon: React.ElementType }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-8 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-muted/60">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <p className="mt-4 font-display text-base font-semibold tracking-tight text-foreground">
        No {platform} posts yet
      </p>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        Once you post on {platform} — or connect an account with existing posts in{' '}
        <strong className="text-foreground/80">Studio → Sources</strong> — they'll show up here
        to reuse and remix.
      </p>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Post card                                                                  */
/* -------------------------------------------------------------------------- */

function SocialPostCard({
  post,
  Icon,
}: {
  post: { url: string; title: string | null; published_at: string | null; image_url: string | null; source_name: string }
  Icon: React.ElementType
}) {
  return (
    <Card className="group flex flex-col overflow-hidden transition-all hover:border-primary/40 hover:shadow-[0_8px_28px_-10px_var(--pau-glow-primary)]">
      {/* Thumbnail */}
      <div className="relative aspect-[4/3] w-full overflow-hidden bg-muted/40">
        {post.image_url ? (
          <img
            src={post.image_url}
            alt={post.title ?? 'Social post'}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Icon className="h-10 w-10 text-muted-foreground/40" />
          </div>
        )}
      </div>

      <CardContent className="flex flex-1 flex-col gap-2 p-4">
        {post.title && (
          <p className="line-clamp-2 text-sm font-medium leading-snug text-foreground/90">
            {post.title}
          </p>
        )}

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          <span className="text-xs text-muted-foreground tabular-nums">
            {relativeDate(post.published_at)}
          </span>
          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-panel-raised hover:text-primary"
            aria-label="Open post"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Open
          </a>
        </div>
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/*  Feed for facebook / instagram                                              */
/* -------------------------------------------------------------------------- */

function SocialFeed({ platform, def }: { platform: 'facebook' | 'instagram'; def: PlatformDef }) {
  const { data, isLoading, isError, refetch, isFetching } = useSocialPosts(platform)
  const posts = data?.posts ?? []

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="aspect-[4/3] animate-pulse rounded-2xl border border-border bg-card"
          />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-8 py-12 text-center">
        <p className="text-sm text-muted-foreground">
          Couldn't load {def.label} posts.{' '}
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        </p>
      </div>
    )
  }

  if (posts.length === 0) {
    return <PlatformEmptyState platform={def.label} Icon={def.Icon} />
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {posts.map((post) => (
        <SocialPostCard key={post.url} post={post} Icon={def.Icon} />
      ))}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Public component                                                           */
/* -------------------------------------------------------------------------- */

export function YourPosts() {
  const [platform, setPlatform] = useState<Platform>('facebook')
  const activeDef = PLATFORMS.find((p) => p.id === platform)!
  const refresh = useRefreshSocials()        // forced, manual Refresh button
  const autoRefresh = useRefreshSocials()    // un-forced, silent on-open background refresh
  const autoRan = useRef(false)

  // Feels-automatic freshness: on open, kick a throttled background refresh (the server skips
  // sources refreshed <30m ago). Cached posts render immediately; the grid repaints when it resolves.
  // A separate instance from the manual button so the button never shows pending during this.
  useEffect(() => {
    if (autoRan.current) return
    autoRan.current = true
    autoRefresh.mutate({})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRefresh = () => {
    refresh.mutate(
      { force: true },
      {
        onSuccess: (data) => {
          const n = data.refreshed.reduce((sum, r) => sum + (r.ingested || 0), 0)
          toast.success(
            n > 0 ? `Pulled ${n} new post${n === 1 ? '' : 's'}` : 'Your socials are up to date',
          )
        },
        onError: () => toast.error("Couldn't refresh — please try again"),
      },
    )
  }

  return (
    <section className="space-y-5">
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
            Your posts
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Browse your published social posts to reuse and remix.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refresh.isPending}
            className="gap-1.5"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refresh.isPending && 'animate-spin')} />
            Refresh
          </Button>
          <PlatformSwitcher selected={platform} onChange={setPlatform} />
        </div>
      </div>

      {/* Content */}
      {platform === 'linkedin' ? (
        <LinkedInInfoState />
      ) : (
        <SocialFeed platform={platform} def={activeDef} />
      )}
    </section>
  )
}
