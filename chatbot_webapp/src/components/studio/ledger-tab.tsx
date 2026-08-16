'use client'
import { useMemo, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { PublishPreviewDialog } from '@/components/publish/publish-preview-dialog'
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '@/components/ui/select'
import { FileText, ChevronDown, ChevronRight, Copy, Trash2, Search, Share2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useLedger, useUpdateLedger, useDeleteLedger } from '@/hooks/use-studio'
import type { LedgerPost } from '@/lib/studio-api'

const STATUSES = ['suggested', 'drafting', 'drafted', 'approved', 'scheduled', 'posted', 'archived']

const STATUS_BADGE: Record<string, 'coral' | 'amber' | 'success' | 'muted' | 'outline'> = {
  suggested: 'amber', drafting: 'muted', drafted: 'outline', approved: 'success',
  scheduled: 'coral', posted: 'success', archived: 'muted',
}

// Posts with finished copy you can actually publish from here.
const PUBLISHABLE = new Set(['drafted', 'approved', 'scheduled'])

function relativeTime(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (Number.isNaN(diff)) return ''
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function LedgerRow({ post }: { post: LedgerPost }) {
  const update = useUpdateLedger()
  const del = useDeleteLedger()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)

  const changeStatus = async (status: string) => {
    if (status === post.status) return
    try { await update.mutateAsync({ id: post.id, status }); toast.success('Status updated') }
    catch { toast.error('Update failed') }
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(post.content || post.title)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Copy failed')
    }
  }
  const remove = async () => {
    try { await del.mutateAsync(post.id); toast.success('Post removed') }
    catch { toast.error('Remove failed') }
    finally { setConfirm(false) }
  }

  const hasDetail = Boolean(post.content || post.brief)
  const canPublish = PUBLISHABLE.has(post.status) && Boolean(post.content)

  return (
    <div className="rounded-lg px-3 py-2.5 transition-colors hover:bg-accent">
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => hasDetail && setOpen((o) => !o)}
          disabled={!hasDetail}
          className={cn('flex min-w-0 items-center gap-2 text-left', hasDetail && 'cursor-pointer')}
        >
          {hasDetail
            ? (open ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />)
            : <span className="h-4 w-4 shrink-0" />}
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{post.title}</span>
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {post.platform && <span className="capitalize">{post.platform}</span>}
              {post.platform && <span aria-hidden>·</span>}
              <span>{relativeTime(post.updated_at || post.created_at)}</span>
            </span>
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge variant={STATUS_BADGE[post.status] ?? 'muted'} className="hidden capitalize sm:inline-flex">{post.status}</Badge>
          <Select value={post.status} onValueChange={changeStatus}>
            <SelectTrigger className="h-9 w-[8.5rem] capitalize"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
            </SelectContent>
          </Select>
          {canPublish && (
            <Button size="icon-sm" variant="ghost" onClick={() => setPublishOpen(true)} aria-label="Post to socials"
              className="text-muted-foreground hover:text-primary" title="Post to socials">
              <Share2 className="h-4 w-4" />
            </Button>
          )}
          <Button size="icon-sm" variant="ghost" onClick={copy} aria-label="Copy post"
            className="text-muted-foreground hover:text-foreground">
            <Copy className="h-4 w-4" />
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={() => setConfirm(true)} aria-label="Delete post"
            className="text-muted-foreground hover:text-destructive">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {open && hasDetail && (
        <div className="mt-2.5 space-y-2.5 rounded-lg border border-border bg-muted/30 p-3 text-sm">
          {post.brief && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Brief</div>
              <p className="mt-0.5 text-muted-foreground leading-relaxed">{post.brief}</p>
            </div>
          )}
          {post.content && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Content</div>
              <p className="mt-0.5 whitespace-pre-wrap text-foreground leading-relaxed">{post.content}</p>
            </div>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title="Delete post?"
        description={`"${post.title}" will be removed from the ledger.`}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
        onCancel={() => setConfirm(false)}
      />
      {publishOpen && (
        <PublishPreviewDialog
          open={publishOpen}
          onOpenChange={setPublishOpen}
          initialCaption={post.content || ''}
          initialImages={[]}
        />
      )}
    </div>
  )
}

export function LedgerTab() {
  const { data } = useLedger()
  const posts = data?.posts ?? []
  const [filter, setFilter] = useState<string>('all')
  const [query, setQuery] = useState('')

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const p of posts) c[p.status] = (c[p.status] ?? 0) + 1
    return c
  }, [posts])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return posts.filter((p) =>
      (filter === 'all' || p.status === filter) &&
      (!q || p.title.toLowerCase().includes(q) || (p.content ?? '').toLowerCase().includes(q)),
    )
  }, [posts, filter, query])

  if (posts.length === 0) {
    return (
      <Card className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
        <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
          <FileText className="h-6 w-6" />
        </span>
        <div className="space-y-1">
          <h3 className="font-display text-lg font-semibold tracking-tight text-foreground">No posts yet</h3>
          <p className="text-sm text-muted-foreground">Posts you draft in chat will show up here with their status.</p>
        </div>
      </Card>
    )
  }

  // Pipeline pills (only statuses that actually exist), preceded by an "All" pill — this doubles as the
  // "what we've worked on" summary the user asked to fold in here.
  const pills = [{ key: 'all', label: 'All', n: posts.length },
    ...STATUSES.filter((s) => counts[s]).map((s) => ({ key: s, label: s, n: counts[s] }))]

  return (
    <div className="space-y-3 reveal-stagger">
      {/* Pipeline summary + filter */}
      <div className="flex flex-wrap items-center gap-1.5">
        {pills.map((p) => (
          <button
            key={p.key}
            onClick={() => setFilter(p.key)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors',
              filter === p.key
                ? 'border-primary/50 bg-primary/10 text-foreground'
                : 'border-border bg-panel/40 text-muted-foreground hover:text-foreground hover:border-border',
            )}
          >
            <span className="font-semibold tabular-nums">{p.n}</span>
            <span className="capitalize">{p.label}</span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search posts by title or content…"
          className="w-full rounded-lg border border-border bg-background/60 py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
        />
      </div>

      {visible.length === 0 ? (
        <Card className="px-6 py-10 text-center text-sm text-muted-foreground">
          No posts match {query ? `"${query}"` : `the "${filter}" filter`}.
        </Card>
      ) : (
        <Card className="divide-y divide-border p-1.5">
          {visible.map((p) => <LedgerRow key={p.id} post={p} />)}
        </Card>
      )}
    </div>
  )
}
