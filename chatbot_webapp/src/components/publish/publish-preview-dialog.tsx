'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Facebook, Instagram, Loader2, X, Plus, AlertTriangle, Calendar, Send, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { useConnections, useConnectSocial } from '@/hooks/use-studio'
import { usePublishPost } from '@/hooks/use-publishing'
import { imagesApi, type Connection } from '@/lib/studio-api'
import { ApiRequestError, useApiClient } from '@platform/auth-ui'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PublishImage {
  id: string
  url: string // signed display URL
}

export interface PublishApproval {
  approved: true
  caption: string
  image_ids: string[]
  targets: string[]
  scheduled_at: string | null
}

export interface PublishPreviewDialogProps {
  open: boolean
  onOpenChange: (v: boolean) => void
  initialCaption: string
  initialImages: PublishImage[]
  postId?: string | null
  // Pre-fill the scheduler with this time (ISO) and open in "Schedule" mode — e.g. a campaign post's
  // planned time. Ignored if the time is in the past.
  initialScheduledAt?: string | null
  // Chat HITL mode: when provided, the dialog hands the user's approval back to the paused agent graph
  // (which runs the same publish machinery server-side) INSTEAD of publishing directly via the API.
  // Cancelling is the parent's `onOpenChange(false)`. The standalone chip omits this.
  onApprove?: (decision: PublishApproval) => void
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Mirror backend publish-capability logic:
 * - Instagram: needs instagram_content_publish scope
 * - Facebook:  needs pages_manage_posts scope
 */
export function canPublish(conn: Connection): boolean {
  if (conn.status !== 'active') return false
  if (conn.provider === 'instagram') return conn.scopes.includes('instagram_content_publish')
  if (conn.provider === 'facebook') return conn.scopes.includes('pages_manage_posts')
  return false
}

function requiredScope(provider: Connection['provider']): string {
  return provider === 'instagram' ? 'instagram_content_publish' : 'pages_manage_posts'
}

const MAX_CAPTION = 2200

function toIso(localDatetimeValue: string): string {
  // <input type="datetime-local"> gives us "YYYY-MM-DDTHH:mm" (local time).
  // Convert to a full ISO string with timezone offset.
  const d = new Date(localDatetimeValue)
  return d.toISOString()
}

function localMinNow(): string {
  // Round up to next minute so the default value is never immediately invalid.
  const d = new Date()
  d.setSeconds(0, 0)
  d.setMinutes(d.getMinutes() + 1)
  // datetime-local needs "YYYY-MM-DDTHH:mm"
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** ISO → "YYYY-MM-DDTHH:mm" (local) for a future time; falls back to the next minute if past/invalid. */
function isoToLocalFuture(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime()) || d.getTime() <= Date.now()) return localMinNow()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ─── Platform checkbox row ────────────────────────────────────────────────────

function ConnectionCheckbox({
  conn,
  checked,
  onChange,
  onReconnect,
}: {
  conn: Connection
  checked: boolean
  onChange: (checked: boolean) => void
  onReconnect: (provider: 'facebook' | 'instagram') => void
}) {
  const publishable = canPublish(conn)

  return (
    <div
      className={cn(
        'flex flex-col gap-0.5 rounded-xl border px-3 py-2.5 transition-colors',
        publishable
          ? checked
            ? 'border-primary/40 bg-primary/5'
            : 'border-transparent hover:border-border hover:bg-accent/40'
          : 'border-transparent opacity-60',
      )}
    >
      <div className="flex items-center gap-2.5">
        <Checkbox
          id={`conn-${conn.id}`}
          checked={checked}
          disabled={!publishable}
          onChange={(e) => onChange(e.currentTarget.checked)}
        />
        <label
          htmlFor={`conn-${conn.id}`}
          className={cn(
            'flex items-center gap-2 text-sm font-medium leading-none select-none',
            publishable ? 'cursor-pointer text-foreground' : 'cursor-not-allowed text-muted-foreground',
          )}
        >
          {conn.provider === 'facebook' ? (
            <Facebook className="h-4 w-4 shrink-0 text-[#1877F2]" />
          ) : (
            <Instagram className="h-4 w-4 shrink-0 text-[#E1306C]" />
          )}
          <span>{conn.display_name}</span>
          <Badge variant="outline" className="shrink-0 capitalize text-xs">
            {conn.provider}
          </Badge>
        </label>
      </div>
      {!publishable && (
        <div className="ml-[calc(1rem+0.625rem)] space-y-1.5">
          <p className="text-xs text-muted-foreground leading-snug">
            {conn.status !== 'active'
              ? 'This account was disconnected — reconnect to enable publishing.'
              : `${conn.provider === 'facebook' ? 'Facebook' : 'Instagram'} publishing needs the `}
            {conn.status === 'active' && (
              <code className="rounded bg-muted px-1 py-0.5 text-[0.7rem] text-foreground/80">
                {requiredScope(conn.provider)}
              </code>
            )}
            {conn.status === 'active' ? ' permission.' : ''}
          </p>
          {conn.status === 'active' && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer select-none hover:text-foreground">
                How to enable
              </summary>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4 leading-snug">
                <li>
                  Open your Meta app's <strong className="text-foreground/80">Facebook Login for
                  Business</strong> configuration.
                </li>
                <li>
                  Add the{' '}
                  <code className="rounded bg-muted px-1 py-0.5">{requiredScope(conn.provider)}</code>{' '}
                  permission and save.
                </li>
                <li>
                  Come back here and click <strong className="text-foreground/80">Reconnect</strong>.
                </li>
              </ol>
              <a
                href="https://developers.facebook.com/apps/"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-primary hover:underline"
              >
                Open Meta app dashboard ↗
              </a>
            </details>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => onReconnect(conn.provider)}
            className="h-7 gap-1.5 text-xs"
          >
            <RefreshCw className="h-3 w-3" />
            Reconnect
          </Button>
        </div>
      )}
    </div>
  )
}

// ─── Image strip ──────────────────────────────────────────────────────────────

function ImageStrip({
  images,
  removed,
  onToggle,
  onAdd,
  uploading,
}: {
  images: PublishImage[]
  removed: Set<string>
  onToggle: (id: string) => void
  onAdd: (files: FileList) => void
  uploading: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground uppercase tracking-wide">
        Images
        <span className="ml-1 font-normal normal-case">(generated in chat — or add your own)</span>
      </Label>
      <div className="flex flex-wrap gap-2">
        {images.map((img) => {
          const isRemoved = removed.has(img.id)
          return (
            <div key={img.id} className="relative h-16 w-16 shrink-0 group">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.url}
                alt="Post image"
                className={cn(
                  'h-16 w-16 rounded-lg object-cover border border-border transition-opacity',
                  isRemoved && 'opacity-30 saturate-0',
                )}
              />
              <button
                type="button"
                onClick={() => onToggle(img.id)}
                className={cn(
                  'absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full text-xs transition-all',
                  isRemoved
                    ? 'bg-primary/80 text-primary-foreground hover:bg-primary'
                    : 'bg-muted-foreground/70 text-background hover:bg-destructive',
                )}
                aria-label={isRemoved ? 'Restore image' : 'Remove image'}
                title={isRemoved ? 'Restore' : 'Remove'}
              >
                {isRemoved ? '+' : <X className="h-3 w-3" />}
              </button>
            </div>
          )
        })}

        {/* Add-your-own tile */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className={cn(
            'flex h-16 w-16 shrink-0 flex-col items-center justify-center gap-0.5 rounded-lg border border-dashed',
            'border-border text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary',
            'disabled:cursor-not-allowed disabled:opacity-60',
          )}
          aria-label="Add your own image"
          title="Add your own image"
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Plus className="h-4 w-4" />
              <span className="text-[10px] leading-none">Add</span>
            </>
          )}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) onAdd(e.target.files)
            e.target.value = '' // allow re-selecting the same file
          }}
        />
      </div>
    </div>
  )
}

// ─── Dialog ───────────────────────────────────────────────────────────────────

type PublishMode = 'now' | 'schedule'

export function PublishPreviewDialog({
  open,
  onOpenChange,
  initialCaption,
  initialImages,
  postId,
  initialScheduledAt,
  onApprove,
}: PublishPreviewDialogProps) {
  const { data: connData, isLoading: connLoading } = useConnections()
  const publish = usePublishPost()
  const connectSocial = useConnectSocial()
  const qc = useQueryClient()
  const apiClient = useApiClient()

  const handleReconnect = useCallback(
    async (provider: 'facebook' | 'instagram') => {
      try {
        const { authorize_url } = await connectSocial(provider, { popup: true })
        const w = window.open(authorize_url, 'social-reconnect', 'popup,width=600,height=720')
        if (!w) {
          toast.error('Allow popups for this site, or reconnect in Studio → Sources')
          return
        }
        let pollId: ReturnType<typeof setInterval> | undefined
        const onMsg = (e: MessageEvent) => {
          if (e.origin !== window.location.origin || e.data?.type !== 'social_result') return
          window.removeEventListener('message', onMsg)
          if (pollId) clearInterval(pollId)
          qc.invalidateQueries({ queryKey: ['studio', 'connections'] })
          const r = String(e.data.result || '')
          if (r.startsWith('connected')) toast.success('Reconnected ✓ — re-checking permissions')
          else toast.error("Reconnect didn't complete — try again")
        }
        window.addEventListener('message', onMsg)
        pollId = setInterval(() => {
          if (w.closed) {
            window.removeEventListener('message', onMsg)
            if (pollId) clearInterval(pollId)
          }
        }, 500)
      } catch {
        toast.error('Could not start the reconnect flow')
      }
    },
    [connectSocial, qc],
  )

  const connections: Connection[] = connData?.connections ?? []

  // ── state ──
  const [caption, setCaption] = useState(initialCaption)
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set())
  const [uploaded, setUploaded] = useState<PublishImage[]>([])
  const [uploading, setUploading] = useState(false)
  const [selectedConns, setSelectedConns] = useState<Set<string>>(new Set())
  const [mode, setMode] = useState<PublishMode>('now')
  const [scheduledAt, setScheduledAt] = useState<string>(localMinNow())
  const [duplicateConfirm, setDuplicateConfirm] = useState(false)

  // Reset local state when dialog opens
  useEffect(() => {
    if (open) {
      setCaption(initialCaption)
      setRemovedIds(new Set())
      setUploaded([])
      const seeded = initialScheduledAt ? isoToLocalFuture(initialScheduledAt) : null
      setMode(seeded ? 'schedule' : 'now')
      setScheduledAt(seeded ?? localMinNow())
      setDuplicateConfirm(false)
      // Default-select publish-capable connections
      const capable = connections.filter(canPublish).map((c) => c.id)
      setSelectedConns(new Set(capable))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // When connections load, update selection with capable ones (they may arrive after open)
  useEffect(() => {
    if (open && !connLoading) {
      setSelectedConns((prev) => {
        if (prev.size > 0) return prev
        return new Set(connections.filter(canPublish).map((c) => c.id))
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connLoading, open])

  // Derived — generated-in-chat images first, then anything the user uploaded here.
  const allImages = [...initialImages, ...uploaded]
  const activeImages = allImages.filter((img) => !removedIds.has(img.id))
  const imageIds = activeImages.map((img) => img.id)
  const selectedConnIds = Array.from(selectedConns)

  const instagramSelected = selectedConnIds.some((id) => {
    const conn = connections.find((c) => c.id === id)
    return conn?.provider === 'instagram'
  })
  const instagramNeedsImage = instagramSelected && activeImages.length === 0

  const isSchedulePast =
    mode === 'schedule' && new Date(scheduledAt) <= new Date()

  const canSubmit =
    selectedConnIds.length > 0 &&
    caption.trim().length > 0 &&
    !instagramNeedsImage &&
    !isSchedulePast &&
    !publish.isPending

  // ── handlers ──
  const toggleConn = useCallback((id: string, checked: boolean) => {
    setSelectedConns((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  const toggleImage = useCallback((id: string) => {
    setRemovedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const handleAddImages = useCallback(
    async (files: FileList) => {
      setUploading(true)
      try {
        const results = await Promise.allSettled(
          Array.from(files).map((f) => imagesApi.upload(apiClient, f)),
        )
        const ok: PublishImage[] = []
        let failed = 0
        for (const r of results) {
          if (r.status === 'fulfilled') ok.push({ id: r.value.id, url: r.value.url })
          else failed++
        }
        if (ok.length) setUploaded((prev) => [...prev, ...ok])
        if (failed) toast.error(`${failed} image${failed > 1 ? 's' : ''} couldn't be added`)
      } finally {
        setUploading(false)
      }
    },
    [apiClient],
  )

  const doPublish = useCallback(
    async (confirm = false) => {
      // Chat HITL mode: hand the decision back to the paused agent graph instead of publishing here.
      // (The agent's publish_post tool runs the same publish machinery server-side after approval.)
      if (onApprove) {
        onApprove({
          approved: true,
          caption: caption.trim(),
          image_ids: imageIds,
          targets: selectedConnIds,
          scheduled_at: mode === 'schedule' ? toIso(scheduledAt) : null,
        })
        return   // parent closes the dialog by clearing the proposal (controlled `open`)
      }
      try {
        const body = {
          targets: selectedConnIds,
          caption: caption.trim(),
          image_ids: imageIds,
          scheduled_at: mode === 'schedule' ? toIso(scheduledAt) : null,
          post_id: postId ?? null,
          confirm: confirm || undefined,
        }
        const res = await publish.mutateAsync(body)
        if (mode === 'schedule') {
          // Scheduling creates no notification row → this action owns its own toast.
          toast.success('Post scheduled ✓')
          onOpenChange(false)
          setDuplicateConfirm(false)
        } else if (res?.status === 'published') {
          // A publish_ok notification row was created server-side; the single
          // NotificationToaster owns the toast. Nudge it to refetch so it fires now.
          qc.invalidateQueries({ queryKey: ['studio', 'notifications'] })
          onOpenChange(false)
          setDuplicateConfirm(false)
        } else if (res?.status === 'failed') {
          // publish_failed notification row exists → the toaster surfaces the reason.
          // Keep the dialog open so the user can adjust/retry.
          qc.invalidateQueries({ queryKey: ['studio', 'notifications'] })
          setDuplicateConfirm(false)
        } else {
          // pending/publishing — a transient is still being retried; no terminal
          // notification row yet, so this action owns the interim toast.
          toast.info("Still publishing — we'll notify you when it's done")
          onOpenChange(false)
          setDuplicateConfirm(false)
        }
      } catch (err: unknown) {
        if (err instanceof ApiRequestError && err.status === 409) {
          setDuplicateConfirm(true)
          return
        }
        toast.error((err instanceof Error ? err.message : null) || 'Publish failed')
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedConnIds, caption, imageIds, mode, scheduledAt, postId, onApprove],
  )

  // ── render ──
  const noConnections = !connLoading && connections.length === 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[40rem] gap-0 p-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Send className="h-4 w-4 text-primary" />
            Post to socials
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Review and publish this draft to your connected accounts.
          </DialogDescription>
        </DialogHeader>

        {/* Scrollable body */}
        <div className="overflow-y-auto max-h-[70vh] px-6 py-5 space-y-5">

          {/* ── Platforms ── */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground uppercase tracking-wide">
              Platforms
            </Label>
            {connLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading accounts…
              </div>
            ) : noConnections ? (
              <div className="rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
                No accounts connected.{' '}
                <span className="text-foreground/70 font-medium">
                  Go to Studio → Sources to connect Facebook or Instagram.
                </span>
              </div>
            ) : (
              <div className="space-y-1">
                {connections.map((conn) => (
                  <ConnectionCheckbox
                    key={conn.id}
                    conn={conn}
                    checked={selectedConns.has(conn.id)}
                    onChange={(checked) => toggleConn(conn.id, checked)}
                    onReconnect={handleReconnect}
                  />
                ))}
              </div>
            )}
          </div>

          {/* ── Caption ── */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="ppd-caption" className="text-xs text-muted-foreground uppercase tracking-wide">
                Caption
              </Label>
              <span
                className={cn(
                  'text-xs tabular-nums',
                  caption.length > MAX_CAPTION ? 'text-destructive font-medium' : 'text-muted-foreground',
                )}
              >
                {caption.length} / {MAX_CAPTION}
              </span>
            </div>
            <Textarea
              id="ppd-caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={12}
              className="resize-y text-sm min-h-[14rem] leading-relaxed"
              placeholder="Write your caption…"
              maxLength={MAX_CAPTION + 100}
            />
          </div>

          {/* ── Images ── */}
          <ImageStrip
            images={allImages}
            removed={removedIds}
            onToggle={toggleImage}
            onAdd={handleAddImages}
            uploading={uploading}
          />

          {/* ── Instagram image warning ── */}
          {instagramNeedsImage && (
            <div className="flex items-start gap-2 rounded-xl border border-amber/40 bg-amber/8 px-3 py-2.5 text-sm text-amber">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>Instagram requires at least one image. Re-add an image above or deselect Instagram.</span>
            </div>
          )}

          {/* ── When ── */}
          <div className="space-y-2.5">
            <Label className="text-xs text-muted-foreground uppercase tracking-wide">
              When
            </Label>
            {/* Segmented toggle */}
            <div className="flex rounded-lg border border-border p-0.5 w-fit gap-0.5 bg-muted/40">
              <button
                type="button"
                onClick={() => setMode('now')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                  mode === 'now'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Send className="h-3.5 w-3.5" />
                Publish now
              </button>
              <button
                type="button"
                onClick={() => setMode('schedule')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                  mode === 'schedule'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Calendar className="h-3.5 w-3.5" />
                Schedule
              </button>
            </div>

            {mode === 'schedule' && (
              <div className="space-y-1">
                <input
                  type="datetime-local"
                  value={scheduledAt}
                  min={localMinNow()}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  className={cn(
                    'rounded-lg border border-input bg-background/60 px-3 py-2 text-sm',
                    'shadow-[inset_0_1px_2px_0_oklch(0_0_0/0.25)] transition-colors',
                    'focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30',
                    isSchedulePast && 'border-destructive focus:border-destructive',
                  )}
                />
                {isSchedulePast && (
                  <p className="text-xs text-destructive">Scheduled time must be in the future.</p>
                )}
              </div>
            )}
          </div>

          {/* ── Duplicate confirm inline banner ── */}
          {duplicateConfirm && (
            <div className="rounded-xl border border-amber/40 bg-amber/8 px-4 py-3 space-y-2.5">
              <p className="text-sm font-medium text-amber flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                This looks identical to a post you already published.
              </p>
              <p className="text-xs text-muted-foreground">
                Post again anyway? This will create a duplicate on your feed.
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="amber"
                  onClick={() => doPublish(true)}
                  disabled={publish.isPending}
                >
                  {publish.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Post anyway
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDuplicateConfirm(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="px-6 py-4 border-t border-border gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={publish.isPending}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => doPublish(false)}
            disabled={!canSubmit || duplicateConfirm}
            className="min-w-[6rem]"
          >
            {publish.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : mode === 'schedule' ? (
              <>
                <Calendar className="h-4 w-4" />
                Schedule
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Publish
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
