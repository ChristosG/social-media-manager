'use client'

import Link from 'next/link'
import { useAuth } from '@platform/auth-ui'
import {
  MessageSquare, Sparkles, PenLine, Calendar, CheckCircle2, Send, Archive,
  Lightbulb, FileText, ArrowUpRight, ArrowRight, Inbox, LayoutGrid,
  CalendarDays, BarChart3, Megaphone,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LogoMark } from '@/components/brand'
import { cn } from '@/lib/utils'
import { useLedger } from '@/hooks/use-studio'
import type { LedgerPost } from '@/lib/studio-api'

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive' | 'coral' | 'amber' | 'success' | 'muted'

// Ordered status groups shown on the dashboard. Each carries its semantic Badge
// variant and a tinted-tile accent class so the icon picks up the same hue.
const STATUS_GROUPS: {
  status: string
  label: string
  icon: React.ElementType
  variant: BadgeVariant
  tile: string
}[] = [
  { status: 'suggested', label: 'Suggested', icon: Lightbulb,    variant: 'amber',   tile: 'bg-amber/10 text-amber' },
  { status: 'drafting',  label: 'Drafting',  icon: PenLine,      variant: 'muted',   tile: 'bg-muted text-muted-foreground' },
  { status: 'drafted',   label: 'Drafted',   icon: FileText,     variant: 'muted',   tile: 'bg-muted text-muted-foreground' },
  { status: 'approved',  label: 'Approved',  icon: CheckCircle2, variant: 'coral',   tile: 'bg-primary/10 text-primary' },
  { status: 'scheduled', label: 'Scheduled', icon: Calendar,     variant: 'amber',   tile: 'bg-amber/10 text-amber' },
  { status: 'posted',    label: 'Posted',    icon: Send,         variant: 'success', tile: 'bg-sage/12 text-sage' },
  { status: 'archived',  label: 'Archived',  icon: Archive,      variant: 'muted',   tile: 'bg-muted text-muted-foreground' },
]

const STATUS_VARIANT: Record<string, BadgeVariant> = Object.fromEntries(
  STATUS_GROUPS.map((g) => [g.status, g.variant]),
)

const QUICK_ACTIONS: {
  href: string
  title: string
  description: string
  icon: React.ElementType
  tile: string
}[] = [
  {
    href: '/chat',
    title: 'Start a post',
    description: 'Ask the assistant for ideas or draft for any platform.',
    icon: MessageSquare,
    tile: 'bg-primary/10 text-primary',
  },
  {
    href: '/workspace?tab=calendar',
    title: 'Content calendar',
    description: "See what's scheduled and spot the empty days.",
    icon: CalendarDays,
    tile: 'bg-amber/10 text-amber',
  },
  {
    href: '/workspace?tab=campaigns',
    title: 'Campaigns',
    description: 'Review & approve a multi-post campaign — then it drafts each one.',
    icon: Megaphone,
    tile: 'bg-primary/10 text-primary',
  },
  {
    href: '/workspace?tab=insights',
    title: 'Insights',
    description: 'How your content is doing, at a glance.',
    icon: BarChart3,
    tile: 'bg-sage/12 text-sage',
  },
  {
    href: '/workspace',
    title: 'Workspace',
    description: 'Browse, schedule & repost your approved posts.',
    icon: LayoutGrid,
    tile: 'bg-amber/10 text-amber',
  },
  {
    href: '/studio',
    title: 'Studio',
    description: 'Brand voice, memory, ledger & capabilities.',
    icon: Sparkles,
    tile: 'bg-sage/12 text-sage',
  },
]

function StatTile({
  label,
  count,
  icon: Icon,
  tile,
}: {
  label: string
  count: number
  icon: React.ElementType
  tile: string
}) {
  return (
    <Card className="transition-colors hover:bg-panel-raised">
      <CardContent className="flex items-center justify-between gap-3 p-4 sm:p-5">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
          <div className="mt-1 font-display text-3xl font-semibold leading-none tracking-tight tabular-nums">
            {count}
          </div>
        </div>
        <div className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-xl', tile)}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  )
}

function formatWhen(iso: string) {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Date.now() - then
  const m = Math.round(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function PostRow({ post }: { post: LedgerPost }) {
  return (
    <div className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-accent">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground transition-colors group-hover:bg-panel-raised">
        <FileText className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">{post.title}</div>
        <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          {post.platform && <span className="capitalize">{post.platform}</span>}
          {post.platform && <span aria-hidden>·</span>}
          <span>{formatWhen(post.updated_at)}</span>
        </div>
      </div>
      <Badge variant={STATUS_VARIANT[post.status] ?? 'outline'} className="shrink-0 capitalize">
        {post.status}
      </Badge>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { data, isLoading } = useLedger()
  const posts = data?.posts ?? []

  // Group posts by status
  const byStatus = Object.fromEntries(
    STATUS_GROUPS.map(({ status }) => [
      status,
      posts.filter((p) => p.status === status),
    ]),
  )

  // Recent activity: last 6 posts sorted by updated_at
  const recent = [...posts]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 6)

  // Stat tiles: prefer the four "headline" statuses, but fall back to whichever
  // groups actually have posts so the row is never empty/misleading.
  const headline = STATUS_GROUPS.filter((g) =>
    ['suggested', 'approved', 'scheduled', 'posted'].includes(g.status),
  )
  const populated = STATUS_GROUPS.filter((g) => byStatus[g.status].length > 0)
  const statTiles = (populated.length > 0 ? populated : headline).slice(0, 4)

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
      {/* Editorial header */}
      <header className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 sm:p-8">
        <div className="pointer-events-none absolute inset-0 bg-ambient opacity-70" />
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-6">
          <div className="reveal-stagger min-w-0">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              <LogoMark className="h-5 w-5" />
              Home
            </div>
            <h1 className="mt-3 font-display text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">
              {user?.display_name ? (
                <>Welcome back, <span className="text-gradient-warm">{user.display_name}</span></>
              ) : (
                <>Your <span className="text-gradient-warm">Social Studio</span></>
              )}
            </h1>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
              Your nonprofit&apos;s social-media studio — every idea, draft, and post in one place.
            </p>
          </div>

          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-[0_4px_18px_-8px_var(--pau-glow-primary)] transition-all hover:brightness-110 hover:shadow-[0_8px_28px_-8px_var(--pau-glow-primary)] active:scale-[0.97]"
          >
            <Sparkles className="h-4 w-4" />
            Start a post
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </header>

      {/* Stat tiles — post ledger by status */}
      <section className="mt-6 sm:mt-8">
        <h2 className="mb-3 font-display text-lg font-semibold tracking-tight text-foreground">
          Post ledger
        </h2>
        {isLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-[5.5rem] animate-pulse rounded-xl border border-border bg-card"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 reveal-stagger sm:gap-4 lg:grid-cols-4">
            {statTiles.map((g) => (
              <StatTile
                key={g.status}
                label={g.label}
                count={byStatus[g.status].length}
                icon={g.icon}
                tile={g.tile}
              />
            ))}
          </div>
        )}
      </section>

      {/* Quick actions + recent activity */}
      <div className="mt-6 grid grid-cols-1 gap-6 sm:mt-8 lg:grid-cols-5">
        {/* Quick actions */}
        <section className="lg:col-span-2">
          <h2 className="mb-3 font-display text-lg font-semibold tracking-tight text-foreground">
            Quick actions
          </h2>
          <div className="grid grid-cols-1 gap-3 reveal-stagger">
            {QUICK_ACTIONS.map((a, i) => (
              <Link key={`${a.href}-${i}`} href={a.href} className="group block">
                <Card className="transition-all group-hover:border-primary/40 group-hover:bg-accent group-hover:shadow-[0_8px_30px_-12px_var(--pau-glow-primary)]">
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className={cn('grid h-11 w-11 shrink-0 place-items-center rounded-xl', a.tile)}>
                      <a.icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-display text-base font-semibold leading-tight tracking-tight text-foreground">
                        {a.title}
                      </div>
                      <div className="mt-0.5 text-sm leading-snug text-muted-foreground">
                        {a.description}
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        {/* Recent activity */}
        <section className="lg:col-span-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
              Recent activity
            </h2>
            <Link
              href="/studio"
              className="inline-flex items-center gap-1 text-sm font-medium text-primary transition-colors hover:text-primary/80"
            >
              View ledger
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <Card>
            <CardContent className="p-2 sm:p-3">
              {isLoading ? (
                <div className="space-y-1">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-[3.25rem] animate-pulse rounded-xl bg-muted/60" />
                  ))}
                </div>
              ) : recent.length === 0 ? (
                <div className="flex flex-col items-center gap-3 px-4 py-12 text-center">
                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary">
                    <Inbox className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-display text-base font-semibold tracking-tight text-foreground">
                      No posts yet
                    </p>
                    <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                      Head to chat and say &ldquo;suggest some posts&rdquo; to get started.
                    </p>
                  </div>
                  <Link
                    href="/chat"
                    className="mt-1 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-[0_4px_18px_-8px_var(--pau-glow-primary)] transition-all hover:brightness-110 active:scale-[0.97]"
                  >
                    <MessageSquare className="h-4 w-4" />
                    Open chat
                  </Link>
                </div>
              ) : (
                <div className="reveal-stagger">
                  {recent.map((p) => (
                    <PostRow key={p.id} post={p} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
