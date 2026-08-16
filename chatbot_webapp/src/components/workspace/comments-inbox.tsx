'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  Facebook, Instagram, MessageCircle, ExternalLink, RefreshCw, Send, X, Sparkles, Link2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import {
  useComments, useCommentSettings, useUpdateCommentSettings,
  usePollComments, useReplyComment, useIgnoreComment,
} from '@/hooks/use-comments'
import type { Comment } from '@/lib/studio-api'

const PLATFORM_ICONS: Record<string, React.ElementType> = { facebook: Facebook, instagram: Instagram }

function relativeDate(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const m = Math.round((Date.now() - then) / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/* -------------------------------------------------------------------------- */
/*  Single comment card                                                        */
/* -------------------------------------------------------------------------- */

function CommentCard({ comment, highlight }: { comment: Comment; highlight?: boolean }) {
  const reply = useReplyComment()
  const ignore = useIgnoreComment()
  const [text, setText] = useState(comment.reply_text || '')
  const Icon = PLATFORM_ICONS[comment.provider] ?? MessageCircle
  const isOpen = comment.status === 'open'

  const postReply = async () => {
    const t = text.trim()
    if (!t) { toast.error('Write a reply first'); return }
    try {
      await reply.mutateAsync({ id: comment.id, text: t })
      toast.success('Reply posted ✓')
    } catch {
      toast.error('Could not post reply')
    }
  }

  const doIgnore = async () => {
    try { await ignore.mutateAsync(comment.id); toast.success('Comment ignored') }
    catch { toast.error('Could not ignore') }
  }

  return (
    <Card
      id={`comment-${comment.id}`}
      className={cn(
        'overflow-hidden scroll-mt-24 transition-shadow',
        highlight && 'ring-2 ring-primary shadow-[0_0_0_4px_var(--pau-glow-primary)]',
      )}
    >
      <CardContent className="space-y-3 p-4">
        {/* Author + meta */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">
                {comment.author_name || 'Someone'}
              </p>
              <p className="text-xs text-muted-foreground">{relativeDate(comment.commented_at)}</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {comment.status === 'replied' && (
              <Badge variant={comment.reply_mode === 'auto' ? 'success' : 'coral'}>
                {comment.reply_mode === 'auto' ? 'Auto-replied' : 'Replied'}
              </Badge>
            )}
            {comment.status === 'ignored' && <Badge variant="muted">Ignored</Badge>}
            {comment.permalink && (
              <Button asChild variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-primary">
                <a href={comment.permalink} target="_blank" rel="noopener noreferrer" aria-label="Open on platform">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            )}
          </div>
        </div>

        {/* Which post is this on? A clickable chip (thumbnail + caption snippet) → opens the post/comment. */}
        {comment.post && (
          <a
            href={comment.post.permalink || comment.permalink || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              'flex items-center gap-2.5 rounded-lg border border-border bg-card/60 px-2.5 py-1.5 transition-colors',
              (comment.post.permalink || comment.permalink) ? 'hover:border-primary/40 hover:bg-accent/40' : 'pointer-events-none',
            )}
            title="Open the post this comment is on"
          >
            {comment.post.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={comment.post.image_url} alt="" className="h-9 w-9 shrink-0 rounded-md object-cover border border-border" />
            ) : (
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
                <MessageCircle className="h-4 w-4" />
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span className="block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/70">On your post</span>
              <span className="block truncate text-xs text-foreground/85">{comment.post.caption || 'View post'}</span>
            </span>
            <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </a>
        )}

        {/* The comment text */}
        <p className="whitespace-pre-wrap rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground/90">
          {comment.message}
        </p>

        {/* Reply: editable when open, read-only otherwise */}
        {isOpen ? (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              AI-suggested reply — edit before posting
            </div>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={2}
              className="resize-y text-sm"
              placeholder="Write a reply…"
            />
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={doIgnore} disabled={ignore.isPending}>
                <X className="h-3.5 w-3.5" />
                Ignore
              </Button>
              <Button size="sm" onClick={postReply} disabled={reply.isPending}>
                <Send className="h-3.5 w-3.5" />
                {reply.isPending ? 'Posting…' : 'Post reply'}
              </Button>
            </div>
          </div>
        ) : comment.reply_text ? (
          <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
            <p className="mb-0.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Send className="h-3 w-3" /> Your reply
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{comment.reply_text}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/*  Needs-scope / empty states                                                 */
/* -------------------------------------------------------------------------- */

function NeedsScope() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/50 px-6 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary">
        <Link2 className="h-6 w-6" />
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold tracking-tight text-foreground">
        Connect a page to manage comments
      </h3>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-muted-foreground">
        To read and reply to comments, connect a Facebook Page or Instagram account with comment
        permissions in Studio → Sources, then reconnect to grant access.
      </p>
      <Button asChild className="mt-5">
        <Link href="/studio">Go to Studio → Sources</Link>
      </Button>
    </div>
  )
}

function InboxEmpty({ status }: { status: string }) {
  const label = status === 'open' ? 'open comments' : status === 'replied' ? 'replies' : 'ignored comments'
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-14 text-center">
      <MessageCircle className="h-8 w-8 text-muted-foreground/60" />
      <p className="mt-3 font-display text-base font-semibold tracking-tight text-foreground">
        No {label} yet
      </p>
      <p className="mt-1.5 max-w-xs text-sm text-muted-foreground">
        New comments on your published posts will appear here. Use <strong>Poll now</strong> to check.
      </p>
    </div>
  )
}

function InboxSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-36 animate-pulse rounded-2xl border border-border bg-card" />
      ))}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Inbox                                                                       */
/* -------------------------------------------------------------------------- */

const FILTERS = [
  { value: 'open', label: 'Open' },
  { value: 'replied', label: 'Replied' },
  { value: 'ignored', label: 'Ignored' },
] as const
type Filter = (typeof FILTERS)[number]['value']

export function CommentsInbox({ focusCommentId, focusStatus }:
  { focusCommentId?: string | null; focusStatus?: string | null } = {}) {
  const [status, setStatus] = useState<Filter>('open')
  const [highlightId, setHighlightId] = useState<string | null>(null)
  const settings = useCommentSettings()
  const { data, isLoading } = useComments(status)
  const updateSettings = useUpdateCommentSettings()
  const poll = usePollComments()

  const canEngage = settings.data?.can_engage ?? data?.can_engage ?? false
  const autoReply = settings.data?.auto_reply_safe ?? false
  const items = data?.items ?? []

  // A comment notification deep-links here with ?comment=<id>&cstatus=<status>. Switch to that status tab
  // so the comment is in view, then scroll to + briefly highlight it once the list has loaded.
  const FILTER_VALUES = FILTERS.map((f) => f.value) as string[]
  useEffect(() => {
    if (focusStatus && FILTER_VALUES.includes(focusStatus)) setStatus(focusStatus as Filter)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusStatus, focusCommentId])

  useEffect(() => {
    if (!focusCommentId || isLoading) return
    if (!items.some((c) => c.id === focusCommentId)) return
    setHighlightId(focusCommentId)
    const el = document.getElementById(`comment-${focusCommentId}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => setHighlightId(null), 2600)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusCommentId, isLoading, items.length, status])

  const onToggleAuto = async (next: boolean) => {
    try {
      await updateSettings.mutateAsync(next)
      toast.success(next ? 'Auto-reply to simple comments on' : 'Auto-reply off')
    } catch {
      toast.error('Could not update setting')
    }
  }

  const onPoll = async () => {
    try {
      const r = await poll.mutateAsync()
      const n = r.new ?? 0
      toast.success(n > 0 ? `${n} new comment(s)` : 'No new comments')
    } catch {
      toast.error('Poll failed')
    }
  }

  if (!settings.isLoading && !canEngage) return <NeedsScope />

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={(v) => setStatus(v as Filter)}>
          <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
            {FILTERS.map((f) => (
              <TabsTrigger key={f.value} value={f.value}>{f.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={autoReply} onCheckedChange={onToggleAuto} disabled={updateSettings.isPending} />
            <span className="hidden sm:inline">Auto-reply to simple comments</span>
            <span className="sm:hidden">Auto-reply</span>
          </label>
          <Button variant="outline" size="sm" onClick={onPoll} disabled={poll.isPending}>
            <RefreshCw className={cn('h-3.5 w-3.5', poll.isPending && 'animate-spin')} />
            Poll now
          </Button>
        </div>
      </div>

      {/* List / states */}
      {isLoading ? (
        <InboxSkeleton />
      ) : items.length === 0 ? (
        <InboxEmpty status={status} />
      ) : (
        <div className="reveal-stagger space-y-4">
          {items.map((c) => <CommentCard key={c.id} comment={c} highlight={c.id === highlightId} />)}
        </div>
      )}
    </div>
  )
}
