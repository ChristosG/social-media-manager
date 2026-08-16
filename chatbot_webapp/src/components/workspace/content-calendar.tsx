'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronLeft, ChevronRight, CalendarDays, Sparkles, MessageSquarePlus, Check } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useCalendar, useReschedule, usePlanDate } from '@/hooks/use-studio'
import type { CalendarItem, LifecycleStage } from '@/lib/studio-api'
import { PostRefineEditor } from '@/components/workspace/post-refine-editor'

/* -------------------------------------------------------------------------- */
/*  Local-date helpers (no UTC shift)                                          */
/* -------------------------------------------------------------------------- */

/** Format a local Date as YYYY-MM-DD without UTC conversion. */
function fmt(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** The LOCAL calendar day a `when` falls on. A timestamp (has time) is bucketed by the viewer's local
 * date — so a post set for "22:00 Greece time" (stored UTC) shows on the right day, not the UTC day.
 * A bare date is kept as-is. */
function bucketKey(when: string): string {
  if (!when) return ''
  if (when.length <= 10) return when
  const d = new Date(when)
  return isNaN(d.getTime()) ? when.slice(0, 10) : fmt(d)
}

/** Seed a <input type="datetime-local"> ("YYYY-MM-DDTHH:mm", local) from a `when`. Bare dates default to noon. */
function toLocalInput(when: string): string {
  let d: Date
  if (when && when.length <= 10) {
    const [y, m, day] = when.split('-').map(Number)
    d = new Date(y, m - 1, day, 12, 0)
  } else {
    d = new Date(when)
  }
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** A datetime-local value → full ISO (UTC) for the API. */
function inputToIso(local: string): string {
  return new Date(local).toISOString()
}

/** A short local time ("10:30 PM") for a chip — only when `when` actually carries a time. */
function fmtTime(when: string): string {
  if (!when || when.length <= 10) return ''
  const d = new Date(when)
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

/** The text to show on a chip / dialog title — the caption, falling back to the title. */
function itemLabel(item: CalendarItem): string {
  return (item.caption || item.title || 'Untitled post').trim()
}

/* -------------------------------------------------------------------------- */
/*  Calendar grid math (Monday-start)                                          */
/* -------------------------------------------------------------------------- */

type GridDay = { date: Date; inMonth: boolean }

function buildGrid(month: Date): GridDay[] {
  const year = month.getFullYear()
  const mon = month.getMonth()
  const firstDay = new Date(year, mon, 1)
  const lastDay = new Date(year, mon + 1, 0)

  // Monday = 0 … Sunday = 6
  const startDow = (firstDay.getDay() + 6) % 7  // 0=Mon,6=Sun
  const endDow   = (lastDay.getDay()  + 6) % 7

  const days: GridDay[] = []

  // Leading days from the previous month
  for (let i = startDow - 1; i >= 0; i--) {
    const d = new Date(year, mon, -i)
    days.push({ date: d, inMonth: false })
  }

  // Days in this month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push({ date: new Date(year, mon, d), inMonth: true })
  }

  // Trailing days to complete the last row
  const trailing = endDow === 6 ? 0 : 6 - endDow
  for (let i = 1; i <= trailing; i++) {
    days.push({ date: new Date(year, mon + 1, i), inMonth: false })
  }

  return days
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

/* -------------------------------------------------------------------------- */
/*  Lifecycle stage → chip styling + badge                                     */
/* -------------------------------------------------------------------------- */

type StageStyle = {
  label: string
  /** chip background + text (tinted, on the day cell) */
  chip: string
  /** dialog badge classes */
  badge: string
}

/** One source of truth for how each lifecycle stage looks — uses only registered Sanctuary tokens
 * (amber/sage/primary/destructive), mirroring campaign-detail's lifecycle colours. There is no cold
 * "blue/info" token in this warm palette, so Approved uses sage (no icon) and Posted uses sage + a
 * check — the same way the post-card lifecycle stepper distinguishes "posted". */
const STAGE_STYLE: Record<LifecycleStage, StageStyle> = {
  drafting:  { label: 'Drafting',  chip: 'bg-amber/15 text-amber',             badge: 'border-amber/25 bg-amber/12 text-amber' },
  drafted:   { label: 'Draft',     chip: 'bg-amber/15 text-amber',             badge: 'border-amber/25 bg-amber/12 text-amber' },
  approved:  { label: 'Approved',  chip: 'bg-sage/12 text-sage',               badge: 'border-sage/25 bg-sage/12 text-sage' },
  scheduled: { label: 'Scheduled', chip: 'bg-primary/15 text-primary',         badge: 'border-primary/25 bg-primary/12 text-primary' },
  posted:    { label: 'Posted',    chip: 'bg-sage/20 text-sage',               badge: 'border-sage/30 bg-sage/15 text-sage' },
  failed:    { label: 'Failed',    chip: 'bg-destructive/15 text-destructive', badge: 'border-destructive/25 bg-destructive/12 text-destructive' },
}

function stageStyle(stage: LifecycleStage | undefined): StageStyle {
  return STAGE_STYLE[stage ?? 'drafted'] ?? STAGE_STYLE.drafted
}

/** A small stage badge for the dialog header (success/failed carry an icon). */
function StageBadge({ stage }: { stage: LifecycleStage | undefined }) {
  const s = stageStyle(stage)
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold', s.badge)}>
      {stage === 'posted' && <Check className="h-3 w-3" />}
      {s.label}
    </span>
  )
}

/* -------------------------------------------------------------------------- */
/*  Edit dialog — caption + (campaign) refine + open-in-chat + reschedule      */
/* -------------------------------------------------------------------------- */

interface EditDialogProps {
  item: CalendarItem | null
  onClose: () => void
}

function EditDialog({ item, onClose }: EditDialogProps) {
  const router = useRouter()
  const reschedule = useReschedule()
  const planDate   = usePlanDate()

  const [dtVal, setDtVal] = useState<string>(() => (item ? toLocalInput(item.when) : ''))

  if (!item) return null

  // Reschedule (PATCH /social/scheduled/{id}) is valid ONLY for a live, pending scheduled row — that's
  // exactly stage 'scheduled'. A drafted/approved post (even one with a lingering canceled scheduled row)
  // moves its planned date via PUT /ledger/{post_id}/plan. Terminal stages (posted/failed) aren't editable.
  const isScheduled = item.stage === 'scheduled'
  const isTerminal = item.stage === 'posted' || item.stage === 'failed'

  // Inline refine needs the campaign authz endpoint — only available when the item is campaign-linked
  // AND carries a ledger post id. Calendar items don't currently surface `campaign_id` (see note in
  // studio-api.ts), so this stays hidden until the backend includes it.
  const canRefine = !!item.campaign_id && !!item.post_id
  const isPending = reschedule.isPending || planDate.isPending

  const handleSave = async () => {
    if (!dtVal) return
    try {
      if (isScheduled) {
        await reschedule.mutateAsync({ id: item.id, when: inputToIso(dtVal) })
      } else {
        const postId = item.post_id ?? item.id
        await planDate.mutateAsync({ postId, planned_at: inputToIso(dtVal) })
      }
      toast.success('Date & time updated')
      onClose()
    } catch {
      toast.error('Could not update the date')
    }
  }

  const openInChat = () => {
    try {
      if (item.campaign_id && item.post_id) {
        sessionStorage.setItem('pending-context', JSON.stringify({
          campaignId: item.campaign_id, postId: item.post_id, kind: 'post',
          label: (item.caption || item.title || 'this post').slice(0, 140) }))
      }
      sessionStorage.setItem('pending-compose', 'Tell me what to change about this post.')
    } catch { /* ignore */ }
    router.push('/chat')
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-2">
            <StageBadge stage={item.stage} />
            {item.platform && (
              <span className="rounded-full border border-border px-2.5 py-0.5 text-xs font-semibold capitalize text-foreground">
                {item.platform}
              </span>
            )}
          </div>
          <DialogTitle className="break-words pr-6 text-base">{item.title || 'Untitled post'}</DialogTitle>
          <DialogDescription>
            {isTerminal
              ? (item.stage === 'posted' ? 'This post has been published.' : 'This post failed to publish.')
              : isScheduled ? 'Reschedule this post or refine its caption.' : 'Set when this post is planned, or refine its caption.'}
          </DialogDescription>
        </DialogHeader>

        {/* Caption (read-only display) */}
        {item.caption && (
          <p className="max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground/90">
            {item.caption}
          </p>
        )}

        {/* Inline refine — only when this calendar item is campaign-linked (refine needs campaign authz). */}
        {canRefine && (
          <PostRefineEditor
            campaignId={item.campaign_id as string}
            postId={item.post_id as string}
            currentCaption={item.caption ?? ''}
            suggestions={item.refine_suggestions ?? []}
          />
        )}

        {/* Reschedule / plan-date — hidden once the post is published or failed (no longer editable). */}
        {!isTerminal && (
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {isScheduled ? 'New date & time' : 'Planned date & time'}
            </label>
            <Input
              type="datetime-local"
              value={dtVal}
              onChange={(e) => setDtVal(e.target.value)}
              className="w-full"
            />
          </div>
        )}
        {isTerminal && item.stage === 'failed' && item.error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{item.error}</p>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="outline" onClick={openInChat} className="sm:mr-auto">
            <MessageSquarePlus className="h-3.5 w-3.5" /> Open in chat
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isPending}>
              {isTerminal ? 'Close' : 'Cancel'}
            </Button>
            {!isTerminal && (
              <Button onClick={handleSave} disabled={isPending || !dtVal}>
                {isPending ? 'Saving…' : 'Save'}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* -------------------------------------------------------------------------- */
/*  Day cell                                                                   */
/* -------------------------------------------------------------------------- */

const MAX_CHIPS = 3

interface DayCellProps {
  day: GridDay
  items: CalendarItem[]
  isSuggested: boolean
  isToday: boolean
  onClickItem: (item: CalendarItem) => void
}

function DayCell({ day, items, isSuggested, isToday, onClickItem }: DayCellProps) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? items : items.slice(0, MAX_CHIPS)
  const overflow = items.length - MAX_CHIPS

  return (
    <div
      className={cn(
        'relative flex min-h-[6rem] flex-col gap-1 rounded-xl border p-1.5 text-xs transition-colors sm:p-2',
        day.inMonth
          ? 'border-border bg-card'
          : 'border-border/40 bg-card/30',
        isToday && day.inMonth && 'border-primary/40 ring-1 ring-primary/20',
      )}
    >
      {/* Day number */}
      <div className="flex items-center justify-between">
        <span
          className={cn(
            'flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium leading-none',
            isToday && day.inMonth
              ? 'bg-primary text-primary-foreground'
              : day.inMonth
              ? 'text-foreground'
              : 'text-muted-foreground/50',
          )}
        >
          {day.date.getDate()}
        </span>
        {isSuggested && day.inMonth && (
          <Sparkles className="h-3 w-3 shrink-0 text-amber" aria-label="Suggested slot" />
        )}
      </div>

      {/* Chips — exactly one per post (backend deduped). */}
      <div className="flex flex-col gap-0.5">
        {visible.map((item) => {
          const t = fmtTime(item.when)
          const label = itemLabel(item)
          return (
            <button
              key={item.id}
              onClick={() => onClickItem(item)}
              title={t ? `${t} · ${label}` : label}
              className={cn(
                'flex w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-left text-[10px] font-medium leading-snug transition-opacity hover:opacity-80',
                stageStyle(item.stage).chip,
              )}
            >
              {item.stage === 'posted' && <Check className="h-2.5 w-2.5 shrink-0" />}
              {t && <span className="shrink-0 tabular-nums opacity-70">{t}</span>}
              <span className="truncate">{label}</span>
            </button>
          )
        })}
        {overflow > 0 && (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="px-1 text-left text-[10px] font-medium text-muted-foreground hover:text-foreground"
          >
            {showAll ? 'Show less' : `+${overflow} more`}
          </button>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Loading skeleton                                                            */
/* -------------------------------------------------------------------------- */

function CalendarSkeleton() {
  return (
    <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
      {WEEKDAYS.map((d) => (
        <div key={d} className="py-1.5 text-center text-[11px] font-medium text-muted-foreground">
          {d}
        </div>
      ))}
      {Array.from({ length: 35 }).map((_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-card/60" />
      ))}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Main component                                                              */
/* -------------------------------------------------------------------------- */

export function ContentCalendar() {
  const today = new Date()
  const [month, setMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const [selected, setSelected] = useState<CalendarItem | null>(null)

  const grid = useMemo(() => buildGrid(month), [month])

  const frm = fmt(grid[0].date)
  const to  = fmt(grid[grid.length - 1].date)

  const { data, isLoading } = useCalendar(frm, to)

  // Group items by YYYY-MM-DD. One item per post — no client-side merge/dedupe (the backend deduped).
  const itemsByDate = useMemo(() => {
    const map: Record<string, CalendarItem[]> = {}
    for (const item of data?.items ?? []) {
      const key = bucketKey(item.when)
      ;(map[key] ??= []).push(item)
    }
    // within a day, order by time (timed first, by clock; date-only after)
    for (const k of Object.keys(map)) {
      map[k].sort((a, b) => (a.when < b.when ? -1 : a.when > b.when ? 1 : 0))
    }
    return map
  }, [data])

  // Group suggested slots by date
  const suggestedDates = useMemo(() => {
    const set = new Set<string>()
    for (const s of data?.suggested ?? []) set.add(bucketKey(s))
    return set
  }, [data])

  const todayStr = fmt(today)
  const monthLabel = `${MONTHS[month.getMonth()]} ${month.getFullYear()}`

  const prevMonth = () => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))
  const nextMonth = () => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))
  const goToday   = () => setMonth(new Date(today.getFullYear(), today.getMonth(), 1))

  return (
    <section className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
            Content calendar
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Every post across its lifecycle — click any chip to reschedule, refine, or open in chat.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={goToday}>
            Today
          </Button>
          <div className="flex items-center rounded-lg border border-border bg-card">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={prevMonth}
              aria-label="Previous month"
              className="rounded-r-none"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[9rem] px-3 text-center text-sm font-medium tabular-nums">
              {monthLabel}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={nextMonth}
              aria-label="Next month"
              className="rounded-l-none"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Legend — one entry per lifecycle stage. */}
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-amber/40" /> Draft
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-sage/30" /> Approved
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-primary/40" /> Scheduled
        </span>
        <span className="flex items-center gap-1">
          <Check className="h-3 w-3 text-sage" /> Posted
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-destructive/40" /> Failed
        </span>
        <span className="flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-amber" /> Suggested slot
        </span>
      </div>

      {/* Grid */}
      {isLoading ? (
        <CalendarSkeleton />
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[40rem]">
            {/* Day-of-week headers */}
            <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
              {WEEKDAYS.map((d) => (
                <div
                  key={d}
                  className="py-1.5 text-center text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                >
                  {d}
                </div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
              {grid.map((day) => {
                const key = fmt(day.date)
                return (
                  <DayCell
                    key={key}
                    day={day}
                    items={itemsByDate[key] ?? []}
                    isSuggested={suggestedDates.has(key)}
                    isToday={key === todayStr}
                    onClickItem={setSelected}
                  />
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Empty state (loaded but no items) */}
      {!isLoading && (data?.items ?? []).length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-10 text-center">
          <CalendarDays className="mb-2 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm font-medium text-foreground/70">No posts in this period</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Schedule or plan posts from the Scheduled and Posts tabs.
          </p>
        </div>
      )}

      {/* Edit dialog */}
      <EditDialog
        item={selected}
        onClose={() => setSelected(null)}
      />
    </section>
  )
}
