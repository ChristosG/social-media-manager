'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  BarChart3,
  TrendingUp,
  Eye,
  Zap,
  MousePointerClick,
  Users,
  Send,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useInsights, useRefreshInsights, useSocialSettings, useSetUtm } from '@/hooks/use-studio'
import { Switch } from '@/components/ui/switch'
import type { InsightsPlatform, InsightsTopPost } from '@/lib/studio-api'
import { PlatformFilter } from './insights/platform-filter'
import { KpiCard } from './insights/kpi-card'
import { TrendChart, type TrendDatum } from './insights/trend-chart'
import { TopPostDialog } from './insights/top-post-dialog'
import { ContentMix } from './insights/content-mix'

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

const FUNNEL_STAGES = ['suggested', 'drafted', 'approved', 'scheduled', 'posted'] as const

const FUNNEL_BAR_COLORS: Record<string, string> = {
  suggested: 'bg-amber/40',
  drafted:   'bg-muted-foreground/30',
  approved:  'bg-primary/50',
  scheduled: 'bg-amber/60',
  posted:    'bg-sage/60',
}
const FUNNEL_COLORS: Record<string, string> = {
  suggested: 'bg-amber/30 text-amber',
  drafted:   'bg-muted text-muted-foreground',
  approved:  'bg-primary/30 text-primary',
  scheduled: 'bg-amber/50 text-amber',
  posted:    'bg-sage/30 text-sage',
}

// One-line plain-language explanations for each KPI's ⓘ tooltip.
const KPI_META = [
  { key: 'reach',       label: 'Reach',       Icon: Eye,                tip: 'Unique people who saw your posts (from Meta), vs the previous period.' },
  { key: 'engagement',  label: 'Engagement',  Icon: Zap,                tip: 'Likes, comments, shares and saves on your posts, vs the previous period.' },
  { key: 'link_clicks', label: 'Link clicks', Icon: MousePointerClick,  tip: 'Taps on links in your posts, vs the previous period.' },
  { key: 'followers',   label: 'Followers',   Icon: Users,              tip: 'Your follower count, and how it changed over the period.' },
  { key: 'published',   label: 'Published',   Icon: Send,               tip: 'Posts you published in this period, vs the previous one.' },
] as const

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

/* -------------------------------------------------------------------------- */
/*  Loading skeleton                                                            */
/* -------------------------------------------------------------------------- */

function InsightsSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[88px] animate-pulse rounded-xl border border-border bg-card" />
        ))}
      </div>
      <div className="h-[240px] animate-pulse rounded-xl border border-border bg-card" />
      <div className="h-[200px] animate-pulse rounded-xl border border-border bg-card" />
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Honest empty / error states from meta_status                                */
/* -------------------------------------------------------------------------- */

function MetaNotice({ status }: { status: 'no_scope' | 'error' }) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-start gap-1 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted/40">
            <BarChart3 className="h-[1.125rem] w-[1.125rem] text-muted-foreground/60" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground/70">
              {status === 'error' ? 'Insights temporarily unavailable' : 'Connect insights permissions'}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {status === 'error'
                ? "We couldn't reach Meta right now — your permissions are fine, check back shortly."
                : 'Grant the insights permission to see reach, engagement and top posts.'}
            </p>
          </div>
        </div>
        {status !== 'error' && (
          <Link
            href="/workspace?tab=socials"
            className="shrink-0 text-xs font-medium text-primary underline-offset-2 transition-colors hover:text-primary/80 hover:underline"
          >
            Connect socials →
          </Link>
        )}
      </CardContent>
    </Card>
  )
}

function GatheringData() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
      <BarChart3 className="mb-3 h-9 w-9 text-muted-foreground/40" />
      <p className="font-display text-base font-semibold tracking-tight text-foreground">
        Gathering data
      </p>
      <p className="mt-1.5 max-w-xs text-sm text-muted-foreground">
        Insights appear after your next posts — reach, engagement and top performers will show up here.
      </p>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Status funnel — small secondary widget                                     */
/* -------------------------------------------------------------------------- */

function StatusFunnel({ funnel }: { funnel: Record<string, number> }) {
  const counts = FUNNEL_STAGES.map((s) => funnel[s] ?? 0)
  const max = Math.max(...counts, 1)
  if (counts.every((c) => c === 0)) return null
  return (
    <Card>
      <CardHeader className="px-5 pb-2 pt-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-primary" />
          <h3 className="font-display text-sm font-semibold tracking-tight text-foreground">
            Content funnel
          </h3>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">Posts at each stage of the workflow</p>
      </CardHeader>
      <CardContent className="px-5 pb-5">
        <div className="space-y-2.5">
          {FUNNEL_STAGES.map((stage, i) => {
            const count = counts[i]
            const pct = (count / max) * 100
            return (
              <div key={stage} className="flex items-center gap-3">
                <span className="w-20 shrink-0 text-right text-xs font-medium capitalize text-muted-foreground">
                  {stage}
                </span>
                <div className="relative h-2.5 flex-1 rounded-full bg-muted/30">
                  <div
                    className={cn('h-full rounded-full transition-all duration-500', FUNNEL_BAR_COLORS[stage])}
                    style={{ width: `${pct}%` }}
                    aria-label={`${stage}: ${count}`}
                  />
                </div>
                <span
                  className={cn(
                    'w-7 shrink-0 rounded-md px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums',
                    FUNNEL_COLORS[stage],
                  )}
                >
                  {count}
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/*  Main component                                                             */
/* -------------------------------------------------------------------------- */

export function InsightsPanel() {
  const [platform, setPlatform] = useState<InsightsPlatform>('all')
  const [activePost, setActivePost] = useState<InsightsTopPost | null>(null)
  const { data, isLoading } = useInsights(platform, 30)
  const refresh = useRefreshInsights()
  const utmSettings = useSocialSettings()
  const setUtm = useSetUtm()
  // Cooldown reported by the last refresh response; > 0 means the button stays disabled.
  const [cooldown, setCooldown] = useState(0)

  const onRefresh = async () => {
    try {
      const res = await refresh.mutateAsync()
      setCooldown(res.cooldown_seconds ?? 0)
      if (res.enqueued) toast.success('Refreshing insights…')
      else if (res.cooldown_seconds > 0) {
        toast.message(`Refresh available in ${Math.ceil(res.cooldown_seconds / 60)}m`)
      }
    } catch {
      toast.error('Could not refresh just now — please try again')
    }
  }

  if (isLoading) return <InsightsSkeleton />

  const metaStatus = data?.meta_status
  const kpis = data?.kpis
  const series = data?.series ?? []
  const topPosts = data?.top_posts ?? []
  const funnel = data?.status_funnel ?? {}

  const cooldownMins = Math.ceil(cooldown / 60)
  const refreshDisabled = refresh.isPending || cooldown > 0

  const utmOn = utmSettings.data?.utm_tagging ?? false

  /* ---- Header: platform filter + refresh control (always shown) ---- */
  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <PlatformFilter value={platform} onChange={setPlatform} />
      <div className="flex items-center gap-2">
        <span className="hidden text-xs text-muted-foreground sm:inline">
          Updated {relativeTime(data?.updated_at)}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={refreshDisabled}
          title={cooldown > 0 ? `Refresh available in ${cooldownMins}m` : undefined}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', refresh.isPending && 'animate-spin')} />
          {cooldown > 0 ? `Available in ${cooldownMins}m` : 'Refresh'}
        </Button>
      </div>
    </div>
  )

  // Hard gate: permission/connection problems get an honest notice instead of empty charts.
  if (metaStatus === 'no_scope' || metaStatus === 'error') {
    return (
      <section className="space-y-4">
        {header}
        <MetaNotice status={metaStatus} />
        <StatusFunnel funnel={funnel} />
      </section>
    )
  }

  const hasKpis = !!kpis
  const hasData = series.length > 0 || topPosts.length > 0 || hasKpis

  const trendData: TrendDatum[] = series.map((p) => ({
    label: new Date(p.week).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    reach: p.reach,
    engagement: p.engagement,
  }))

  // Per-KPI sparkline from the weekly series (reach/engagement only — others have no series).
  const reachSpark = series.map((p) => p.reach)
  const engagementSpark = series.map((p) => p.engagement)
  const sparkFor = (key: string) =>
    key === 'reach' ? reachSpark : key === 'engagement' ? engagementSpark : undefined

  return (
    <section className="space-y-4">
      {header}

      {!hasData ? (
        <GatheringData />
      ) : (
        <>
          {/* ---- KPI trend cards ---- */}
          {hasKpis && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {KPI_META.map(({ key, label, Icon, tip }) => {
                const kpi = kpis?.[key]
                return (
                  <KpiCard
                    key={key}
                    label={label}
                    Icon={Icon}
                    value={kpi?.value ?? 0}
                    deltaPct={kpi?.delta_pct ?? 0}
                    tooltip={tip}
                    spark={sparkFor(key)}
                  />
                )
              })}
            </div>
          )}

          {/* ---- Reach & engagement trend ---- */}
          {trendData.length > 0 && (
            <Card>
              <CardHeader className="px-5 pb-2 pt-5">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  <h3 className="font-display text-sm font-semibold tracking-tight text-foreground">
                    Reach &amp; engagement
                  </h3>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">Weekly, last 30 days</p>
              </CardHeader>
              <CardContent className="px-5 pb-5">
                <TrendChart data={trendData} />
                <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--color-chart-1)' }} />
                    Reach
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--color-chart-3)' }} />
                    Engagement
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ---- Top posts leaderboard ---- */}
          {topPosts.length > 0 && (
            <Card>
              <CardHeader className="px-5 pb-2 pt-5">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-primary" />
                  <h3 className="font-display text-sm font-semibold tracking-tight text-foreground">
                    Top posts
                  </h3>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">Your best performers this period</p>
              </CardHeader>
              <CardContent className="px-5 pb-4">
                <ul className="divide-y divide-border/60">
                  {topPosts.map((post, i) => (
                    <li key={post.post_id}>
                      <button
                        type="button"
                        onClick={() => setActivePost(post)}
                        className="flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-panel-raised/40 -mx-2 rounded-lg px-2"
                      >
                        <span className="w-4 shrink-0 text-center text-xs font-semibold tabular-nums text-muted-foreground/70">
                          {i + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm text-foreground/90">
                          {post.caption || <span className="italic text-muted-foreground">No caption</span>}
                        </span>
                        <span className="flex shrink-0 items-center gap-3 text-xs tabular-nums text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Eye className="h-3 w-3" />
                            {post.reach.toLocaleString()}
                          </span>
                          <span className="flex items-center gap-1">
                            <Zap className="h-3 w-3" />
                            {post.engagement.toLocaleString()}
                          </span>
                        </span>
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/40" />
                      </button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* ---- Content mix + status funnel (secondary) ---- */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ContentMix data={data?.content_mix} />
        <StatusFunnel funnel={funnel} />
      </div>

      {/* ---- Attribution: opt-in UTM tagging (off by default) ---- */}
      <Card>
        <CardContent className="flex items-start justify-between gap-4 px-5 py-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">Tag links for attribution</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Add <span className="font-mono">utm_*</span> tags to links when publishing, so you can see social
              traffic in your own analytics (Google Analytics, etc.). Makes public URLs a little longer.
            </p>
          </div>
          <Switch
            checked={utmOn}
            disabled={utmSettings.isLoading || setUtm.isPending}
            onCheckedChange={(v) => setUtm.mutate(v)}
            aria-label="Toggle UTM link tagging on publish"
          />
        </CardContent>
      </Card>

      <TopPostDialog
        post={activePost}
        open={!!activePost}
        onOpenChange={(o) => !o && setActivePost(null)}
      />
    </section>
  )
}
