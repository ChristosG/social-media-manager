'use client'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '@/components/ui/select'
import {
  Tooltip, TooltipTrigger, TooltipContent, TooltipProvider,
} from '@/components/ui/tooltip'
import {
  Globe, RefreshCw, Trash2, ChevronDown, ChevronRight, ExternalLink, Plus, Loader2,
  Facebook, Instagram, Link2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import {
  useSources, useCreateSource, useRefreshSource,
  useSourceDocuments, useDeleteSource,
  useConnections, useAddConnectionSource, useDisconnect, useConnectSocial,
} from '@/hooks/use-studio'
import type { Source, Connection } from '@/lib/studio-api'

// ─── helpers ──────────────────────────────────────────────────────────────────

type SourceType = 'auto' | 'single' | 'section' | 'rss'

const TYPE_LABELS: Record<SourceType, string> = {
  auto: 'Auto-detect',
  single: 'Single page',
  section: 'Section (latest N)',
  rss: 'RSS feed',
}

const STATUS_BADGE: Record<Source['last_status'], 'muted' | 'success' | 'amber' | 'destructive'> = {
  pending: 'muted',
  ok: 'success',
  partial: 'amber',
  failed: 'destructive',
}

const STATUS_LABEL: Record<Source['last_status'], string> = {
  pending: 'Ingesting…',
  ok: 'Active',
  partial: 'Partial',
  failed: 'No content',
}

function relativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

// ─── Article list panel ───────────────────────────────────────────────────────

function ArticlePanel({ sourceId }: { sourceId: string }) {
  const { data, isLoading } = useSourceDocuments(sourceId, true)
  const docs = data?.documents ?? []

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2.5 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading articles…
      </div>
    )
  }

  if (docs.length === 0) {
    return <p className="px-3 py-2.5 text-sm text-muted-foreground">No articles yet.</p>
  }

  return (
    <div className="divide-y divide-border">
      {docs.map((doc) => (
        <div key={doc.id} className="flex items-start justify-between gap-3 px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-sm text-foreground">{doc.title ?? doc.url}</p>
            <p className="text-xs text-muted-foreground">
              {doc.published_at
                ? `Published ${relativeTime(doc.published_at)} · `
                : ''}
              Fetched {relativeTime(doc.fetched_at)}
              {doc.char_count ? ` · ${(doc.char_count / 1000).toFixed(1)}k chars` : ''}
            </p>
          </div>
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Open article"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      ))}
    </div>
  )
}

// ─── Single source row ────────────────────────────────────────────────────────

function SourceRow({ source }: { source: Source }) {
  const refresh = useRefreshSource()
  const del = useDeleteSource()
  const [expanded, setExpanded] = useState(false)
  const [confirm, setConfirm] = useState(false)

  const isRefreshing = refresh.isPending && refresh.variables === source.id

  const handleRefresh = async () => {
    try {
      const result = await refresh.mutateAsync(source.id)
      toast.success(`Refreshed — ${result.ingested} new, ${result.skipped} unchanged`)
    } catch {
      toast.error('Refresh failed')
    }
  }

  const handleDelete = async () => {
    try {
      await del.mutateAsync(source.id)
      toast.success('Source removed')
    } catch {
      toast.error('Remove failed')
    } finally {
      setConfirm(false)
    }
  }

  const statusBadge = STATUS_BADGE[source.last_status]
  const statusLabel = STATUS_LABEL[source.last_status]

  return (
    <div className="rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-accent/50">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => setExpanded((o) => !o)}
          className="flex min-w-0 items-center gap-2 text-left cursor-pointer"
          aria-expanded={expanded}
        >
          {expanded
            ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{source.name}</span>
            <span className="block truncate text-xs text-muted-foreground" title={source.config.url}>
              {source.config.url}
            </span>
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-1.5">
          {/* Health badge — wrap in tooltip if there's an error */}
          {source.last_status === 'failed' && source.last_error ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Badge variant={statusBadge}>{statusLabel}</Badge>
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">{source.last_error}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Badge variant={statusBadge}>{statusLabel}</Badge>
          )}

          {/* detected kind */}
          {source.detected_kind && (
            <Badge variant="outline" className="hidden sm:inline-flex capitalize">
              {source.detected_kind}
            </Badge>
          )}

          {/* refresh time */}
          <span className="hidden text-xs text-muted-foreground sm:inline">
            {source.last_refreshed_at ? `refreshed ${relativeTime(source.last_refreshed_at)}` : 'not yet refreshed'}
          </span>

          {/* Refresh now */}
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label={`Refresh ${source.name}`}
            className="text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
          </Button>

          {/* Delete */}
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => setConfirm(true)}
            aria-label={`Delete ${source.name}`}
            className="text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Expanded article panel */}
      {expanded && (
        <div className="mt-2.5 rounded-lg border border-border bg-muted/30 overflow-hidden">
          <ArticlePanel sourceId={source.id} />
        </div>
      )}

      <ConfirmDialog
        open={confirm}
        title="Delete source?"
        description={`"${source.name}" and all its articles will be removed from your knowledge base.`}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setConfirm(false)}
      />
    </div>
  )
}

// ─── Social connection row ────────────────────────────────────────────────────

function ConnectionRow({ conn }: { conn: Connection }) {
  const addSource = useAddConnectionSource()
  const disconnect = useDisconnect()
  const connectSocial = useConnectSocial()
  const [confirm, setConfirm] = useState(false)

  const handleReconnect = async () => {
    try {
      const res = await connectSocial(conn.provider)
      window.location.href = res.authorize_url
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 503) {
        toast.error('Set up your Meta app first — see docs/meta-social-setup.md')
      } else {
        toast.error('Could not start reconnect flow')
      }
    }
  }

  const handleAddSource = async () => {
    try {
      await addSource.mutateAsync(conn.id)
      toast.success('Pulling your posts…')
    } catch {
      toast.error('Failed to add as source')
    }
  }

  const handleDisconnect = async () => {
    try {
      await disconnect.mutateAsync(conn.id)
      toast.success('Disconnected')
    } catch {
      toast.error('Disconnect failed')
    } finally {
      setConfirm(false)
    }
  }

  const isAdding = addSource.isPending && addSource.variables === conn.id
  const isDisconnecting = disconnect.isPending && disconnect.variables === conn.id

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-accent/50">
      <div className="flex items-center gap-2.5 min-w-0">
        {conn.provider === 'facebook'
          ? <Facebook className="h-4 w-4 shrink-0 text-[#1877F2]" />
          : <Instagram className="h-4 w-4 shrink-0 text-[#E1306C]" />}
        <span className="truncate text-sm font-medium text-foreground">{conn.display_name}</span>
        <Badge variant="outline" className="shrink-0 capitalize">{conn.provider}</Badge>
        {conn.status === 'active' && <Badge variant="success">Active</Badge>}
        {conn.status === 'needs_reconnect' && <Badge variant="amber">Reconnect</Badge>}
        {conn.status === 'revoked' && <Badge variant="muted">Revoked</Badge>}
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        {conn.status === 'needs_reconnect' && (
          <Button size="sm" variant="outline" onClick={handleReconnect} className="text-xs">
            Reconnect
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={handleAddSource}
          disabled={isAdding}
          className="text-xs"
        >
          {isAdding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5" />}
          {isAdding ? 'Adding…' : 'Add as source'}
        </Button>
        <Button
          size="icon-sm"
          variant="ghost"
          onClick={() => setConfirm(true)}
          disabled={isDisconnecting}
          aria-label={`Disconnect ${conn.display_name}`}
          className="text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <ConfirmDialog
        open={confirm}
        title="Disconnect account?"
        description={`"${conn.display_name}" will be disconnected. Sources created from it will remain until you delete them.`}
        confirmLabel="Disconnect"
        destructive
        onConfirm={handleDisconnect}
        onCancel={() => setConfirm(false)}
      />
    </div>
  )
}

// ─── Connect social accounts card ─────────────────────────────────────────────

function SocialConnectionsCard() {
  const { data, isLoading } = useConnections()
  const connectSocial = useConnectSocial()
  const [connecting, setConnecting] = useState<'facebook' | 'instagram' | null>(null)
  const connections = data?.connections ?? []

  const handleConnect = async (provider: 'facebook' | 'instagram') => {
    setConnecting(provider)
    try {
      const res = await connectSocial(provider)
      window.location.href = res.authorize_url
    } catch (err: unknown) {
      setConnecting(null)
      const status = (err as { status?: number })?.status
      if (status === 503) {
        toast.error('Set up your Meta app first — see docs/meta-social-setup.md')
      } else {
        toast.error('Could not start connect flow')
      }
    }
  }

  return (
    <Card className="p-5 space-y-4">
      <div className="space-y-1">
        <h3 className="font-display text-base font-semibold tracking-tight text-foreground">
          Connect your social accounts
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Connect Instagram or Facebook to ground drafts in your own past posts.
          (One-time setup: <span className="font-mono text-xs">docs/meta-social-setup.md</span>.)
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleConnect('facebook')}
          disabled={connecting !== null}
          className="gap-2"
        >
          {connecting === 'facebook'
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Facebook className="h-4 w-4 text-[#1877F2]" />}
          Connect Facebook
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleConnect('instagram')}
          disabled={connecting !== null}
          className="gap-2"
        >
          {connecting === 'instagram'
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Instagram className="h-4 w-4 text-[#E1306C]" />}
          Connect Instagram
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading connections…
        </div>
      )}

      {!isLoading && connections.length > 0 && (
        <div className="space-y-0.5">
          {connections.map((conn) => <ConnectionRow key={conn.id} conn={conn} />)}
        </div>
      )}
    </Card>
  )
}

// ─── Add source form (inline card) ───────────────────────────────────────────

function AddSourceForm() {
  const create = useCreateSource()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [type, setType] = useState<SourceType>('auto')

  const canSubmit = name.trim().length > 0 && url.trim().length > 0

  const handleSubmit = async () => {
    if (!canSubmit) return
    try {
      await create.mutateAsync({ name: name.trim(), url: url.trim(), type })
      toast.success('Added — ingesting in the background…')
      setName('')
      setUrl('')
      setType('auto')
    } catch {
      toast.error('Add failed — check the URL and try again.')
    }
  }

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="font-display text-base font-semibold tracking-tight text-foreground">Add a source</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Add a site, section, or article. We pull the latest articles, keep them fresh, and ground your
            chat in them — toggle &ldquo;Ground in my sources&rdquo; in the composer.
          </p>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto_auto]">
        <div className="space-y-1.5">
          <Label htmlFor="source-name">Name</Label>
          <Input
            id="source-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. ACLU News"
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="source-url">URL</Label>
          <Input
            id="source-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.org/news"
            type="url"
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="source-type">Type</Label>
          <Select value={type} onValueChange={(v) => setType(v as SourceType)}>
            <SelectTrigger id="source-type" className="w-[11rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.entries(TYPE_LABELS) as [SourceType, string][]).map(([v, label]) => (
                <SelectItem key={v} value={v}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-end">
          <Button
            disabled={!canSubmit || create.isPending}
            onClick={handleSubmit}
            className="w-full sm:w-auto"
          >
            {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus />}
            {create.isPending ? 'Adding…' : 'Add'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

// ─── Sources tab ──────────────────────────────────────────────────────────────

export function SourcesTab() {
  const { data, isLoading } = useSources()
  const sources = data?.sources ?? []

  return (
    <div className="space-y-4 reveal-stagger">
      <SocialConnectionsCard />
      <AddSourceForm />

      {isLoading && (
        <div className="flex items-center gap-2 px-1 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading sources…
        </div>
      )}

      {!isLoading && sources.length === 0 && (
        <Card className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
            <Globe className="h-6 w-6" />
          </span>
          <div className="space-y-1">
            <h3 className="font-display text-lg font-semibold tracking-tight text-foreground">No sources yet</h3>
            <p className="text-sm text-muted-foreground">
              Add a URL above and the assistant will ground its answers in real articles from that site.
            </p>
          </div>
        </Card>
      )}

      {!isLoading && sources.length > 0 && (
        <Card className="space-y-0.5 p-2">
          {sources.map((s) => <SourceRow key={s.id} source={s} />)}
        </Card>
      )}
    </div>
  )
}
