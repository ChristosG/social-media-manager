'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  Calendar, Eye, Pencil, Plus, MoreHorizontal, Copy, Trash2,
  CheckCircle2, Send, Instagram, Linkedin, Facebook, Music2, Hash,
  Globe, ArrowRight, LayoutList, Globe2, CalendarClock, MessageCircle,
  CalendarDays, BarChart3, Megaphone, DownloadCloud,
} from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '@/components/ui/dialog'
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { LogoMark } from '@/components/brand'
import { cn } from '@/lib/utils'
import { useLedger, useUpdateLedger, useDeleteLedger } from '@/hooks/use-studio'
import type { LedgerPost } from '@/lib/studio-api'
import { PublishPreviewDialog } from '@/components/publish/publish-preview-dialog'
import { YourPosts } from '@/components/workspace/your-posts'
import { ScheduledPosts } from '@/components/workspace/scheduled-posts'
import { CommentsInbox } from '@/components/workspace/comments-inbox'
import { ContentCalendar } from '@/components/workspace/content-calendar'
import { InsightsPanel } from '@/components/workspace/insights-panel'
import { CampaignsPanel } from '@/components/workspace/campaigns-panel'

/* -------------------------------------------------------------------------- */
/*  Status + platform presentation                                            */
/* -------------------------------------------------------------------------- */

type BadgeVariant = 'coral' | 'amber' | 'success' | 'muted' | 'outline'

// The Workspace is the library of finished/working posts. "suggested" and
// "drafting" are raw ideas / in-progress — they live in chat & Studio, not here.
const WORK_STATUSES = ['drafted', 'approved', 'scheduled', 'posted'] as const
type WorkStatus = (typeof WORK_STATUSES)[number]

// Statuses we offer in the Edit dialog's status Select (the full work lifecycle).
const EDIT_STATUSES = ['drafted', 'approved', 'scheduled', 'posted', 'archived']

const STATUS_META: Record<WorkStatus, { label: string; variant: BadgeVariant }> = {
  drafted: { label: 'Drafted', variant: 'muted' },
  approved: { label: 'Approved', variant: 'coral' },
  scheduled: { label: 'Scheduled', variant: 'amber' },
  posted: { label: 'Posted', variant: 'success' },
}

// Map ledger platform strings (lowercase) → icon + display label. Falls back to
// a globe for anything we don't have a brand glyph for.
const PLATFORM_META: Record<string, { icon: React.ElementType; label: string }> = {
  instagram: { icon: Instagram, label: 'Instagram' },
  linkedin: { icon: Linkedin, label: 'LinkedIn' },
  facebook: { icon: Facebook, label: 'Facebook' },
  x: { icon: Hash, label: 'X' },
  twitter: { icon: Hash, label: 'X' },
  tiktok: { icon: Music2, label: 'TikTok' },
}

function platformMeta(platform: string | null) {
  if (!platform) return null
  return (
    PLATFORM_META[platform.toLowerCase()] ?? {
      icon: Globe,
      label: platform.charAt(0).toUpperCase() + platform.slice(1),
    }
  )
}

// Segmented filter — 'all' = the four work statuses; the rest pin to one status.
const FILTERS: { value: 'all' | WorkStatus; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'drafted', label: 'Drafted' },
  { value: 'approved', label: 'Approved' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'posted', label: 'Posted' },
]

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                    */
/* -------------------------------------------------------------------------- */

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

function previewText(post: LedgerPost) {
  return post.content || post.brief || post.title
}

/* -------------------------------------------------------------------------- */
/*  Post card                                                                 */
/* -------------------------------------------------------------------------- */

function PostCard({ post }: { post: LedgerPost }) {
  const update = useUpdateLedger()
  const del = useDeleteLedger()

  const [editOpen, setEditOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [draft, setDraft] = useState(post.content ?? '')
  const [draftStatus, setDraftStatus] = useState(post.status)

  // Publish dialog state
  const [publishOpen, setPublishOpen] = useState(false)

  const plat = platformMeta(post.platform)
  const status = STATUS_META[post.status as WorkStatus] ?? {
    label: post.status.charAt(0).toUpperCase() + post.status.slice(1),
    variant: 'outline' as BadgeVariant,
  }
  const isApproved = post.status === 'approved'
  const isPosted = post.status === 'posted'
  const isScheduled = post.status === 'scheduled'

  const setStatus = async (next: WorkStatus, message: string) => {
    try {
      await update.mutateAsync({ id: post.id, status: next })
      toast.success(message)
    } catch {
      toast.error('Something went wrong')
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(post.content || post.title)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Copy failed')
    }
  }

  const openEdit = () => {
    setDraft(post.content ?? '')
    setDraftStatus(post.status)
    setEditOpen(true)
  }

  const saveEdit = async () => {
    try {
      await update.mutateAsync({ id: post.id, content: draft, status: draftStatus })
      toast.success('Post updated')
      setEditOpen(false)
    } catch {
      toast.error('Update failed')
    }
  }

  const remove = async () => {
    try {
      await del.mutateAsync(post.id)
      toast.success('Post removed')
    } catch {
      toast.error('Remove failed')
    } finally {
      setConfirmOpen(false)
    }
  }

  return (
    <>
      <Card className="group flex h-full flex-col transition-all hover:border-primary/40 hover:bg-panel-raised hover:shadow-[0_10px_36px_-14px_var(--pau-glow-primary)]">
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 p-4 pb-3">
          <div className="flex min-w-0 items-center gap-2">
            {plat && (
              <Badge variant="outline" className="gap-1.5">
                <plat.icon className="h-3.5 w-3.5" />
                {plat.label}
              </Badge>
            )}
            <Badge variant={status.variant}>{status.label}</Badge>
            {post.origin === 'imported' && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-[0.7rem] font-medium text-sky-500">
                    <DownloadCloud className="h-3 w-3" /> Imported
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  Imported from {plat?.label ?? 'your account'} — not created in Social Studio.
                </TooltipContent>
              </Tooltip>
            )}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="-mr-1 shrink-0 text-muted-foreground hover:text-foreground"
                aria-label="Post actions"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem onSelect={openEdit}>
                <Eye className="h-4 w-4" />
                View &amp; edit
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={copy}>
                <Copy className="h-4 w-4" />
                Copy text
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {!isApproved && (
                <DropdownMenuItem onSelect={() => setStatus('approved', 'Post approved')}>
                  <CheckCircle2 className="h-4 w-4" />
                  Approve
                </DropdownMenuItem>
              )}
              {!isScheduled && !isPosted && (
                <DropdownMenuItem onSelect={() => setStatus('scheduled', 'Post scheduled')}>
                  <Calendar className="h-4 w-4" />
                  Schedule
                </DropdownMenuItem>
              )}
              {!isPosted && (
                <DropdownMenuItem onSelect={() => setStatus('posted', 'Marked as posted')}>
                  <Send className="h-4 w-4" />
                  Mark posted
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => setConfirmOpen(true)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardHeader>

        <CardContent className="flex-1 p-4 pt-0">
          <p className="line-clamp-4 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
            {previewText(post)}
          </p>
        </CardContent>

        <CardFooter className="items-center justify-between gap-2 border-t border-border/60 p-4 pt-3">
          <div className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{formatWhen(post.updated_at)}</span>
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            {/* Post / Schedule button — opens PublishPreviewDialog */}
            {!isPosted && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPublishOpen(true)}
                className="gap-1.5"
              >
                <Send className="h-3.5 w-3.5" />
                Post
              </Button>
            )}

            {!isApproved && !isPosted ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setStatus('approved', 'Post approved')}
                disabled={update.isPending}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Approve
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={openEdit}
              className="text-muted-foreground hover:text-primary"
              aria-label="Edit post"
            >
              <Pencil className="h-4 w-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Publish dialog */}
      <PublishPreviewDialog
        open={publishOpen}
        onOpenChange={setPublishOpen}
        initialCaption={post.content ?? post.brief ?? post.title ?? ''}
        initialImages={[]}
        postId={post.id}
      />

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{post.title}</DialogTitle>
            <DialogDescription>
              Edit the post content and status. Changes save to your ledger.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Content
              </label>
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={8}
                className="resize-y"
                placeholder="Write the post copy…"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Status
              </label>
              <Select value={draftStatus} onValueChange={setDraftStatus}>
                <SelectTrigger className="w-[12rem] capitalize">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EDIT_STATUSES.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveEdit} disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete post?"
        description={`"${post.title}" will be removed from your workspace.`}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
        onCancel={() => setConfirmOpen(false)}
      />
    </>
  )
}

/* -------------------------------------------------------------------------- */
/*  Empty + loading states                                                    */
/* -------------------------------------------------------------------------- */

// Shown when the whole workspace (all work statuses) is empty — premium CTA.
function WorkspaceEmpty() {
  return (
    <div className="reveal-stagger flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/50 px-6 py-16 text-center sm:py-20">
      <div className="grid h-16 w-16 place-items-center rounded-2xl bg-primary/10">
        <LogoMark className="h-9 w-9" />
      </div>
      <h2 className="mt-5 font-display text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
        Your workspace is waiting
      </h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        Drafted, approved, scheduled, and posted work collects here — ready to refine and publish.
        Start one in chat and bring it to life.
      </p>
      <Button asChild className="mt-6">
        <Link href="/chat">
          <Plus className="h-4 w-4" />
          Start a post
        </Link>
      </Button>
    </div>
  )
}

// Shown when a specific filter is empty but other work exists — lighter note.
function FilterEmpty({ filterLabel }: { filterLabel: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-14 text-center">
      <p className="font-display text-base font-semibold tracking-tight text-foreground">
        Nothing in {filterLabel.toLowerCase()} yet
      </p>
      <p className="mt-1.5 max-w-xs text-sm text-muted-foreground">
        Posts move here as they reach the {filterLabel.toLowerCase()} stage.
      </p>
    </div>
  )
}

function WorkspaceSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="h-[12.5rem] animate-pulse rounded-2xl border border-border bg-card"
        />
      ))}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Ledger (posts) tab content                                                */
/* -------------------------------------------------------------------------- */

function LedgerTab() {
  const [filter, setFilter] = useState<'all' | WorkStatus>('all')
  const { data, isLoading } = useLedger()

  // Only the work statuses belong in the Workspace.
  const workPosts = useMemo(
    () => (data?.posts ?? []).filter((p) => (WORK_STATUSES as readonly string[]).includes(p.status)),
    [data],
  )

  // Per-filter counts for the segmented control.
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: workPosts.length }
    for (const s of WORK_STATUSES) c[s] = 0
    for (const p of workPosts) if (p.status in c) c[p.status] += 1
    return c
  }, [workPosts])

  const visible = useMemo(() => {
    const list = filter === 'all' ? workPosts : workPosts.filter((p) => p.status === filter)
    // Most recently touched first.
    return [...list].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
  }, [workPosts, filter])

  const activeFilterLabel = FILTERS.find((f) => f.value === filter)?.label ?? 'All'
  const workspaceEmpty = !isLoading && workPosts.length === 0

  return (
    <div className="space-y-6">
      {/* Status filter */}
      {!workspaceEmpty && (
        <Tabs value={filter} onValueChange={(v) => setFilter(v as 'all' | WorkStatus)}>
          <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
            {FILTERS.map((f) => (
              <TabsTrigger key={f.value} value={f.value}>
                {f.label}
                <span className="ml-1.5 text-xs tabular-nums opacity-70">{counts[f.value] ?? 0}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      {/* Grid / states */}
      {isLoading ? (
        <WorkspaceSkeleton />
      ) : workspaceEmpty ? (
        <WorkspaceEmpty />
      ) : visible.length === 0 ? (
        <FilterEmpty filterLabel={activeFilterLabel} />
      ) : (
        <div className="reveal-stagger grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}

      {/* Footer hint */}
      {!isLoading && !workspaceEmpty && visible.length > 0 && (
        <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          Need something new?
          <Link
            href="/chat"
            className="inline-flex items-center gap-1 font-medium text-primary transition-colors hover:text-primary/80"
          >
            Draft a post in chat
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                      */
/* -------------------------------------------------------------------------- */

type PageTab = 'posts' | 'socials' | 'scheduled' | 'comments' | 'calendar' | 'insights' | 'campaigns'
const PAGE_TABS: PageTab[] = ['posts', 'socials', 'scheduled', 'comments', 'calendar', 'insights', 'campaigns']

function WorkspacePageInner() {
  const [pageTab, setPageTab] = useState<PageTab>('posts')
  const searchParams = useSearchParams()
  const tabParam = searchParams.get('tab')
  const focusCommentId = searchParams.get('comment')
  const focusStatus = searchParams.get('cstatus')

  // Deep-link from a comment notification (/workspace?tab=comments&comment=<id>&cstatus=<status>) — open the
  // tab on arrival AND when the query changes while already here (clicking a notification from this page).
  // useSearchParams is reactive, so this fires on every notification click, not just first mount.
  useEffect(() => {
    if (tabParam && (PAGE_TABS as string[]).includes(tabParam)) setPageTab(tabParam as PageTab)
  }, [tabParam, focusCommentId])

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
      {/* Editorial header */}
      <header className="reveal-stagger flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            <LogoMark className="h-5 w-5" />
            Workspace
          </div>
          <h1 className="mt-3 font-display text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">
            Your <span className="text-gradient-warm">workspace</span>
          </h1>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
            Your drafted, approved, scheduled & posted work — ready to refine and publish.
          </p>
        </div>

        <Button asChild size="lg">
          <Link href="/chat">
            <Plus className="h-4 w-4" />
            New post
          </Link>
        </Button>
      </header>

      {/* Top-level page tabs */}
      <div className="mt-6 sm:mt-8">
        <Tabs value={pageTab} onValueChange={(v) => setPageTab(v as PageTab)}>
          <TabsList className="w-full justify-start">
            <TabsTrigger value="posts">
              <LayoutList className="h-4 w-4" />
              Posts
            </TabsTrigger>
            <TabsTrigger value="socials">
              <Globe2 className="h-4 w-4" />
              Your socials
            </TabsTrigger>
            <TabsTrigger value="scheduled">
              <CalendarClock className="h-4 w-4" />
              Scheduled
            </TabsTrigger>
            <TabsTrigger value="comments">
              <MessageCircle className="h-4 w-4" />
              Comments
            </TabsTrigger>
            <TabsTrigger value="calendar">
              <CalendarDays className="h-4 w-4" />
              Calendar
            </TabsTrigger>
            <TabsTrigger value="insights">
              <BarChart3 className="h-4 w-4" />
              Insights
            </TabsTrigger>
            <TabsTrigger value="campaigns">
              <Megaphone className="h-4 w-4" />
              Campaigns
            </TabsTrigger>
          </TabsList>

          <TabsContent value="posts">
            <LedgerTab />
          </TabsContent>

          <TabsContent value="socials">
            <YourPosts />
          </TabsContent>

          <TabsContent value="scheduled">
            <ScheduledPosts />
          </TabsContent>

          <TabsContent value="comments">
            <CommentsInbox focusCommentId={focusCommentId} focusStatus={focusStatus} />
          </TabsContent>

          <TabsContent value="calendar">
            <ContentCalendar />
          </TabsContent>

          <TabsContent value="insights">
            <InsightsPanel />
          </TabsContent>

          <TabsContent value="campaigns">
            <CampaignsPanel />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

// useSearchParams must be inside a Suspense boundary for the production build.
export default function WorkspacePage() {
  return (
    <Suspense fallback={null}>
      <WorkspacePageInner />
    </Suspense>
  )
}
