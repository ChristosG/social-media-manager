'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useApiClient } from '@platform/auth-ui'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ChevronDown, ChevronRight, ImagePlus, Sparkles, Calendar, Send, Loader2, X,
  MessageSquarePlus, ExternalLink, Check, AlertTriangle, Clock, Trash2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { cn } from '@/lib/utils'
import {
  useUpdateCampaignPost, usePlanDate, useSetPostImages, useGeneratePostImage, useApproveCampaignPost,
  useDeleteCampaignSlot,
} from '@/hooks/use-studio'
import { imagesApi, type CampaignSlot, type LifecycleStage } from '@/lib/studio-api'
import { PublishPreviewDialog } from '@/components/publish/publish-preview-dialog'
import { PostRefineEditor } from '@/components/workspace/post-refine-editor'

/* ----------------------------- date helpers ------------------------------ */

function toLocalInput(when: string | null | undefined): string {
  if (!when) return ''
  const d = new Date(when.length <= 10 ? `${when}T12:00:00` : when)
  if (isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
function inputToIso(local: string): string { return new Date(local).toISOString() }
function fmtWhen(when: string | null | undefined): string {
  if (!when) return 'No date yet'
  const d = new Date(when.length <= 10 ? `${when}T12:00:00` : when)
  if (isNaN(d.getTime())) return 'No date yet'
  return d.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

/* --------------------------- lifecycle stepper --------------------------- */

const ORDER: LifecycleStage[] = ['drafting', 'drafted', 'approved', 'scheduled', 'posted']
const STEPS: { key: LifecycleStage; label: string }[] = [
  { key: 'drafted', label: 'Drafted' },
  { key: 'approved', label: 'Approved' },
  { key: 'scheduled', label: 'Scheduled' },
  { key: 'posted', label: 'Posted' },
]

function LifecycleStepper({ stage, permalink, error }: { stage: LifecycleStage; permalink: string | null; error: string | null }) {
  if (stage === 'failed') {
    return (
      <div className="flex items-center gap-1.5 text-xs text-destructive">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">Publish failed{error ? ` — ${error}` : ''}</span>
      </div>
    )
  }
  const reached = ORDER.indexOf(stage)
  return (
    <div className="flex items-center gap-1.5">
      {STEPS.map((s, i) => {
        const done = ORDER.indexOf(s.key) <= reached
        const isPosted = s.key === 'posted' && stage === 'posted'
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            {i > 0 && <span className={cn('h-px w-3', done ? 'bg-sage/50' : 'bg-border')} />}
            <span className={cn(
              'flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
              done ? 'bg-sage/12 text-sage' : 'bg-muted text-muted-foreground',
            )}>
              {done && <Check className="h-2.5 w-2.5" />}
              {isPosted && permalink ? (
                <a href={permalink} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 hover:underline">
                  {s.label} <ExternalLink className="h-2.5 w-2.5" />
                </a>
              ) : s.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* -------------------------------- card ----------------------------------- */

export function CampaignPostCard({ slot, campaignId, filling = false }:
  { slot: CampaignSlot; campaignId: string; filling?: boolean }) {
  const router = useRouter()
  const api = useApiClient()
  const qc = useQueryClient()
  const updatePost = useUpdateCampaignPost()
  const planDate = usePlanDate()
  const setImages = useSetPostImages()
  const genImage = useGeneratePostImage()
  const approvePost = useApproveCampaignPost()
  const deleteSlot = useDeleteCampaignSlot()
  const fileRef = useRef<HTMLInputElement>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const doDelete = async () => {
    try { await deleteSlot.mutateAsync({ campaignId, slotId: slot.id }); toast.success('Post removed') }
    catch { toast.error('Could not remove — a published post must be unscheduled first') }
    finally { setConfirmDelete(false) }
  }

  const deleteButton = (
    <button
      type="button" aria-label="Delete this post"
      onClick={(e) => { e.stopPropagation(); setConfirmDelete(true) }}
      className="absolute right-2 top-2 z-10 grid h-7 w-7 place-items-center rounded-md text-muted-foreground/60 transition-colors hover:bg-destructive/10 hover:text-destructive"
    >
      <Trash2 className="h-3.5 w-3.5" />
    </button>
  )

  const confirmDialog = (
    <ConfirmDialog
      open={confirmDelete}
      title="Delete this post?"
      description="This post will be removed from the campaign. This can't be undone."
      confirmLabel="Delete" destructive
      onConfirm={doDelete} onCancel={() => setConfirmDelete(false)}
    />
  )

  const post = slot.post ?? null
  const lc = slot.lifecycle ?? { stage: 'drafting' as LifecycleStage, permalink: null, error: null, scheduled_at: null, published_at: null }

  const [expanded, setExpanded] = useState(false)
  const [caption, setCaption] = useState(post?.caption ?? '')
  const [dtVal, setDtVal] = useState(toLocalInput(post?.planned_at))
  const [scheduleOpen, setScheduleOpen] = useState(false)

  // Sync the caption when the SERVER value changes (e.g. the post was just drafted by 'Draft all', or refined
  // in chat) — without this the editor stayed empty until a full page reload. We never clobber an in-progress
  // edit: adopt the new server caption only while the field still matches the previous server value.
  const serverCaption = post?.caption ?? ''
  const prevServerCaption = useRef(serverCaption)
  useEffect(() => {
    if (serverCaption !== prevServerCaption.current) {
      setCaption((local) => (local === prevServerCaption.current ? serverCaption : local))
      prevServerCaption.current = serverCaption
    }
  }, [serverCaption])

  // No post yet. Distinguish ACTIVELY drafting (spinner) from merely PROPOSED/awaiting (no spinner) —
  // a proposed campaign must never look like it's working when it isn't.
  if (!post) {
    return (
      <div className="relative flex items-center gap-2 rounded-2xl border border-dashed border-border bg-card/40 py-3 pl-4 pr-9 text-sm text-muted-foreground">
        {deleteButton}
        {confirmDialog}
        {filling ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="truncate">Drafting: {slot.angle}</span>
          </>
        ) : (
          <>
            <ImagePlus className="h-4 w-4 shrink-0 text-muted-foreground/50" />
            <span className="truncate"><span className="text-foreground/70">Not yet drafted</span> · {slot.angle}</span>
          </>
        )}
      </div>
    )
  }

  const images = post.images ?? []
  const dirty = caption !== (post.caption ?? '') || (dtVal && dtVal !== toLocalInput(post.planned_at))
  const busy = updatePost.isPending || planDate.isPending

  const save = async () => {
    try {
      if (caption !== (post.caption ?? '')) await updatePost.mutateAsync({ id: post.id, content: caption })
      if (dtVal && dtVal !== toLocalInput(post.planned_at)) await planDate.mutateAsync({ postId: post.id, planned_at: inputToIso(dtVal) })
      toast.success('Post updated')
      setExpanded(false)
    } catch { toast.error('Could not save — please try again') }
  }

  const onUpload = async (files: FileList) => {
    try {
      const up = await imagesApi.upload(api, files[0])
      await setImages.mutateAsync({ id: post.id, image_ids: [...images.map((i) => i.id), up.id] })
      toast.success('Image added')
    } catch { toast.error('Upload failed') }
  }
  const onGenerate = async () => {
    try { await genImage.mutateAsync({ id: post.id, prompt: caption || slot.angle }); toast.success('Image generated') }
    catch { toast.error('Could not generate an image just now') }
  }
  const onRemoveImage = async (id: string) => {
    try { await setImages.mutateAsync({ id: post.id, image_ids: images.filter((i) => i.id !== id).map((i) => i.id) }) }
    catch { toast.error('Could not remove the image') }
  }

  const refineInChat = () => {
    try {
      // Bind the chat turn to this exact post so the assistant edits the right caption (+ landing shows it).
      sessionStorage.setItem('pending-context', JSON.stringify({
        campaignId, postId: post.id, kind: 'post', label: (caption || slot.angle || 'this post').slice(0, 140) }))
      sessionStorage.setItem('pending-compose', 'Tell me what to change about this post.')
    } catch { /* ignore */ }
    router.push('/chat')
  }

  // Review gate: a freshly drafted post must be APPROVED before it can be scheduled. Approve/Schedule are
  // shown as a single primary next-step so the flow reads draft → review → approve → schedule.
  const needsApproval = lc.stage === 'drafted'
  const isApproved = lc.stage === 'approved'
  const onApprove = async () => {
    try {
      // persist any unsaved caption edits first, so you approve exactly what you reviewed
      if (caption !== (post.caption ?? '')) await updatePost.mutateAsync({ id: post.id, content: caption })
      await approvePost.mutateAsync({ campaignId, postId: post.id })
      toast.success('Approved — ready to schedule')
    } catch { toast.error('Could not approve — please try again') }
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/30">
      {deleteButton}
      {confirmDialog}
      {/* Read header (click to expand) */}
      <button onClick={() => setExpanded((v) => !v)} className="flex w-full items-start gap-3 py-3 pl-4 pr-9 text-left" aria-expanded={expanded}>
        {/* thumb */}
        {images[0] ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={images[0].url} alt="" className="h-14 w-14 shrink-0 rounded-lg border border-border object-cover" />
        ) : (
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-lg border border-dashed border-border text-muted-foreground/50">
            <ImagePlus className="h-5 w-5" />
          </span>
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 font-medium text-foreground/80">
              <Clock className="h-3 w-3" /> {fmtWhen(post.planned_at)}
            </span>
            {slot.platform && <Badge variant="outline" className="capitalize">{slot.platform}</Badge>}
            <LifecycleStepper stage={lc.stage} permalink={lc.permalink} error={lc.error} />
          </div>
          <p className={cn('text-sm leading-relaxed text-foreground/90', !expanded && 'line-clamp-2')}>
            {post.caption || <span className="italic text-muted-foreground">No caption yet</span>}
          </p>
        </div>
        <span className="mt-1 shrink-0 text-muted-foreground">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>

      {/* Inline editor */}
      {expanded && (
        <div className="space-y-4 border-t border-border/60 bg-muted/15 px-4 py-4">
          {/* caption */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Caption</label>
            <Textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={5} className="resize-y text-sm leading-relaxed" placeholder="Write the post caption…" />
            {/* Inline tailored refine chips → diff → Apply/Undo, while the post is still editable. */}
            {(needsApproval || isApproved) && (
              <PostRefineEditor
                campaignId={campaignId}
                postId={post.id}
                currentCaption={caption}
                suggestions={post.refine_suggestions}
                onApplied={setCaption}
                onReverted={setCaption}
              />
            )}
          </div>

          {/* date + images row */}
          <div className="flex flex-wrap gap-4">
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Date &amp; time</label>
              <input type="datetime-local" value={dtVal} onChange={(e) => setDtVal(e.target.value)}
                className="block rounded-lg border border-input bg-background/60 px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Images</label>
              <div className="flex flex-wrap items-center gap-2">
                {images.map((img) => (
                  <div key={img.id} className="relative h-14 w-14 shrink-0">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={img.url} alt="" className="h-14 w-14 rounded-lg border border-border object-cover" />
                    <button onClick={() => onRemoveImage(img.id)} aria-label="Remove image"
                      className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-muted-foreground/70 text-background hover:bg-destructive">
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                <button onClick={() => fileRef.current?.click()} disabled={setImages.isPending}
                  className="grid h-14 w-14 shrink-0 place-items-center rounded-lg border border-dashed border-border text-muted-foreground hover:border-primary/50 hover:text-primary disabled:opacity-60"
                  aria-label="Upload image" title="Upload your own">
                  {setImages.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
                </button>
                <button onClick={onGenerate} disabled={genImage.isPending}
                  className="grid h-14 w-14 shrink-0 place-items-center gap-0.5 rounded-lg border border-dashed border-border text-muted-foreground hover:border-primary/50 hover:text-primary disabled:opacity-60"
                  aria-label="Generate image" title="Generate with AI">
                  {genImage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                </button>
                <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden"
                  onChange={(e) => { if (e.target.files?.length) onUpload(e.target.files); e.target.value = '' }} />
              </div>
            </div>
          </div>

          {/* actions */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button size="sm" onClick={save} disabled={!dirty || busy}>
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Save
            </Button>
            <Button size="sm" variant="outline" onClick={refineInChat}>
              <MessageSquarePlus className="h-3.5 w-3.5" /> Refine in chat
            </Button>
            {isApproved && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-sage">
                <Check className="h-3.5 w-3.5" /> Approved
              </span>
            )}
            {needsApproval ? (
              <Button size="sm" className="ml-auto" onClick={onApprove}
                disabled={approvePost.isPending || updatePost.isPending}>
                {approvePost.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Approve
              </Button>
            ) : (
              <Button size="sm" variant="secondary" className="ml-auto" onClick={() => setScheduleOpen(true)}>
                {lc.stage === 'scheduled' || lc.stage === 'posted'
                  ? (<><Calendar className="h-3.5 w-3.5" /> Reschedule</>)
                  : (<><Send className="h-3.5 w-3.5" /> Schedule to accounts</>)}
              </Button>
            )}
          </div>
        </div>
      )}

      <PublishPreviewDialog
        open={scheduleOpen}
        onOpenChange={(o) => { setScheduleOpen(o); if (!o) qc.invalidateQueries({ queryKey: ['campaign'] }) }}
        initialCaption={post.caption ?? ''}
        initialImages={images}
        postId={post.id}
        initialScheduledAt={post.planned_at}
      />
    </div>
  )
}
