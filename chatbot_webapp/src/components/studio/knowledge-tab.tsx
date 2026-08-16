'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '@/components/ui/select'
import {
  Brain, Trash2, Plus, RefreshCw, Globe, Instagram, Facebook, Rss, Activity,
  ExternalLink, Clock, Loader2, BookMarked, ShieldAlert, Check,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import {
  useMemory, useCreateMemory, useDeleteMemory,
  usePendingMemory, useApproveMemory,
  useSources, useSourceStats, useRefreshSource,
  useTraceStatus, useTraces,
} from '@/hooks/use-studio'
import type { MemoryEntry, Source } from '@/lib/studio-api'

// ── Learned preferences ──────────────────────────────────────────────────────
// Every editable memory KIND, with the value-field it lives under and a friendly label. This is the
// full surface (the curated Memory tab only exposes voice/banned/pillars); here a non-engineer can see
// and prune EVERYTHING the assistant has learned, including rules it captured itself mid-conversation.
const KINDS: { kind: string; label: string; field: string; placeholder: string }[] = [
  { kind: 'brand_voice', label: 'Brand voice', field: 'descriptor', placeholder: 'warm and grassroots' },
  { kind: 'banned_topic', label: 'Banned topic', field: 'topic', placeholder: 'party politics' },
  { kind: 'content_pillar', label: 'Content pillar', field: 'name', placeholder: 'volunteer stories' },
  { kind: 'style_rule', label: 'Style rule', field: 'rule', placeholder: 'always sign off with 🐾' },
  { kind: 'cta_pref', label: 'Call-to-action', field: 'cta', placeholder: 'end with our donation link' },
  { kind: 'hashtag_pref', label: 'Hashtag preference', field: 'text', placeholder: '#AdoptDontShop' },
  { kind: 'fact', label: 'Fact', field: 'text', placeholder: 'Founded in 2014 in Athens' },
]
const KIND_META = Object.fromEntries(KINDS.map((k) => [k.kind, k]))

const SOURCE_BADGE: Record<string, string> = {
  user_correction: 'You taught this',
  research: 'From research',
  inferred: 'Inferred',
  manual: 'Added manually',
}

function entryText(e: MemoryEntry): string {
  const v = e.value || {}
  const meta = KIND_META[e.kind]
  if (meta && v[meta.field] != null) return String(v[meta.field])
  // Unknown kind / shape — show the first stringy value, else compact JSON.
  const first = Object.values(v).find((x) => typeof x === 'string')
  return (first as string) ?? JSON.stringify(v)
}

function PendingReviewCard() {
  const { data } = usePendingMemory()
  const approve = useApproveMemory()
  const del = useDeleteMemory()
  const entries = data?.entries ?? []
  if (entries.length === 0) return null   // only appears when something is actually awaiting review

  const ok = async (id: string) => {
    try { await approve.mutateAsync(id); toast.success('Approved — now active') }
    catch { toast.error('Approve failed') }
  }
  const reject = async (id: string) => {
    try { await del.mutateAsync(id); toast.success('Discarded') }
    catch { toast.error('Discard failed') }
  }

  return (
    <Card className="border-amber-500/40 bg-amber-500/[0.03]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-amber-500">
          <ShieldAlert className="h-5 w-5" /> Awaiting your review
          <Badge variant="amber" className="ml-1 text-[10px]">{entries.length}</Badge>
        </CardTitle>
        <CardDescription>
          The assistant proposed these while reading external sources (a website, news, or web search). To
          stop a malicious page from silently rewriting your brand, they stay <em>inactive</em> until you
          approve them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1.5">
        {entries.map((e) => (
          <div key={e.id} className="flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-panel/40 px-3 py-2">
            <div className="min-w-0 flex-1">
              <span className="block truncate text-sm text-foreground">{entryText(e)}</span>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {KIND_META[e.kind]?.label ?? e.kind}
              </span>
            </div>
            <Button size="sm" variant="outline" onClick={() => ok(e.id)} disabled={approve.isPending}
              className="shrink-0 border-emerald-500/40 text-emerald-500 hover:bg-emerald-500/10">
              <Check className="h-4 w-4" /> Approve
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={() => reject(e.id)} aria-label="Discard"
              className="shrink-0 text-muted-foreground hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function LearnedPreferencesCard() {
  const { data, isLoading } = useMemory()
  const create = useCreateMemory()
  const del = useDeleteMemory()
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [addKind, setAddKind] = useState('style_rule')
  const [addValue, setAddValue] = useState('')

  const entries = data?.entries ?? []
  const grouped = useMemo(() => {
    const m = new Map<string, MemoryEntry[]>()
    for (const e of entries) { (m.get(e.kind) ?? m.set(e.kind, []).get(e.kind)!).push(e) }
    return m
  }, [entries])

  const add = async () => {
    const v = addValue.trim()
    if (!v) return
    const field = KIND_META[addKind]?.field ?? 'text'
    try {
      await create.mutateAsync({ kind: addKind, value: { [field]: v } })
      setAddValue(''); toast.success('Saved to memory')
    } catch { toast.error('Save failed') }
  }
  const remove = async (id: string) => {
    try { await del.mutateAsync(id); toast.success('Removed') }
    catch { toast.error('Remove failed') }
    finally { setConfirmId(null) }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Brain className="h-5 w-5" /> Learned preferences</CardTitle>
        <CardDescription>
          Everything the assistant has learned about your org — including rules it picked up from your
          corrections in chat. Edits apply on the next message.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add row */}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select value={addKind} onValueChange={setAddKind}>
            <SelectTrigger className="h-9 w-full sm:w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              {KINDS.map((k) => <SelectItem key={k.kind} value={k.kind}>{k.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <input
            value={addValue}
            onChange={(e) => setAddValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') add() }}
            placeholder={KIND_META[addKind]?.placeholder}
            className="h-9 flex-1 rounded-md border border-border bg-background px-3 text-sm outline-none focus:border-primary/50"
          />
          <Button onClick={add} disabled={!addValue.trim() || create.isPending} className="shrink-0">
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>

        {isLoading ? (
          <div className="py-6 text-center text-muted-foreground"><Loader2 className="inline h-5 w-5 animate-spin" /></div>
        ) : entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Nothing learned yet — correct the assistant in chat (&quot;too corporate&quot;, &quot;never mention X&quot;)
            and it&apos;ll remember here.
          </p>
        ) : (
          <div className="space-y-4">
            {KINDS.filter((k) => grouped.has(k.kind)).map((k) => (
              <div key={k.kind}>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{k.label}</div>
                <div className="space-y-1.5">
                  {grouped.get(k.kind)!.map((e) => (
                    <div key={e.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-panel/30 px-3 py-2">
                      <span className="min-w-0 flex-1 truncate text-sm text-foreground">{entryText(e)}</span>
                      <Badge variant="outline" className="hidden shrink-0 text-[10px] sm:inline-flex">
                        {SOURCE_BADGE[e.source] ?? e.source}
                      </Badge>
                      <Button size="icon-sm" variant="ghost" onClick={() => setConfirmId(e.id)}
                        aria-label="Remove" className="shrink-0 text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <ConfirmDialog
        open={confirmId !== null}
        title="Remove this?"
        description="The assistant will stop applying this preference."
        confirmLabel="Remove"
        destructive
        onConfirm={() => confirmId && remove(confirmId)}
        onCancel={() => setConfirmId(null)}
      />
    </Card>
  )
}

// ── Knowledge & sources ──────────────────────────────────────────────────────
function sourceIcon(kind: string) {
  if (kind === 'instagram') return Instagram
  if (kind === 'facebook') return Facebook
  if (kind === 'rss') return Rss
  return Globe
}
const STATUS_BADGE: Record<string, 'success' | 'amber' | 'muted' | 'coral'> = {
  ok: 'success', partial: 'amber', pending: 'muted', failed: 'coral',
}
function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function SourceRow({ source }: { source: Source }) {
  const { data: statsData } = useSourceStats()
  const refresh = useRefreshSource()
  const Icon = sourceIcon(source.detected_kind || source.kind)
  const stats = statsData?.stats?.[source.id]
  const reingest = async () => {
    try {
      const r = await refresh.mutateAsync(source.id)
      toast.success(`Re-ingested — ${r.ingested} new, ${r.skipped} unchanged`)
    } catch { toast.error('Re-ingest failed') }
  }
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-panel/30 px-3 py-2.5">
      <div className="flex min-w-0 items-center gap-2.5">
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">{source.name}</div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant={STATUS_BADGE[source.last_status] ?? 'muted'} className="text-[10px]">{source.last_status}</Badge>
            <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{relTime(source.last_refreshed_at)}</span>
            {stats && <span>{stats.documents} docs · {stats.chunks} chunks</span>}
          </div>
        </div>
      </div>
      <Button size="sm" variant="ghost" onClick={reingest} disabled={refresh.isPending}
        className="shrink-0 text-muted-foreground hover:text-foreground">
        <RefreshCw className={cn('h-4 w-4', refresh.isPending && 'animate-spin')} /> Re-ingest
      </Button>
    </div>
  )
}

function KnowledgeSourcesCard() {
  const { data } = useSources()
  const sources = data?.sources ?? []
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><BookMarked className="h-5 w-5" /> Knowledge base</CardTitle>
        <CardDescription>
          What the assistant has ingested to ground its answers — your website, feeds, and your own
          social posts. Re-ingest to pull the latest.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sources.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No sources yet — add a website/feed or connect a social account in the Sources tab.
          </p>
        ) : (
          <div className="space-y-1.5">{sources.map((s) => <SourceRow key={s.id} source={s} />)}</div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Recent agent activity (observability-lite) ───────────────────────────────
function RecentActivityCard() {
  const { data: status } = useTraceStatus()
  const { data: traces } = useTraces(8)
  if (!status?.enabled) return null   // tracing not configured — hide rather than show an empty card
  const items = traces?.traces ?? []
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5" /> Recent agent activity</CardTitle>
            <CardDescription>The last few turns the assistant handled. Click any turn to open its full step-by-step trace.</CardDescription>
          </div>
          <Link href="/settings?tab=observability"
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-panel/60 hover:text-foreground">
            Full traces <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <div className="space-y-1.5">
            {items.map((t) => (
              <Link
                key={t.id}
                href={`/settings?tab=observability&trace=${t.id}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-panel/30 px-3 py-2 transition-colors hover:border-primary/40 hover:bg-panel/60"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-foreground">{t.user_message || t.name || 'agent turn'}</span>
                {t.latency != null && (
                  <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                    {t.latency < 1 ? `${Math.round(t.latency * 1000)} ms` : `${t.latency.toFixed(1)} s`}
                  </span>
                )}
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function KnowledgeTab() {
  return (
    <div className="space-y-4 reveal-stagger">
      <PendingReviewCard />
      <LearnedPreferencesCard />
      <KnowledgeSourcesCard />
      <RecentActivityCard />
    </div>
  )
}
