'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Activity, Loader2, ChevronRight, ExternalLink, Cpu, Wrench, Workflow,
  AlertTriangle, User, Bot, Clock, Eye, EyeOff, Copy, Check,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTraceStatus, useTraces, useTrace } from '@/hooks/use-studio'
import type { TraceStep, StepCategory } from '@/lib/studio-api'

function fmtMs(s: number | null): string {
  if (s == null) return '—'
  const ms = s * 1000
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`
}
function fmtTime(t: string | null): string {
  if (!t) return ''
  try { return new Date(t).toLocaleString() } catch { return t }
}

const CAT_META: Record<StepCategory, { icon: typeof Cpu; label: string; cls: string }> = {
  llm: { icon: Cpu, label: 'model', cls: 'text-violet-300 bg-violet-500/10 border-violet-500/20' },
  tool: { icon: Wrench, label: 'tool', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/20' },
  node: { icon: Workflow, label: 'graph', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/20' },
  plumbing: { icon: Workflow, label: 'internal', cls: 'text-muted-foreground bg-panel/40 border-border' },
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1200) }}
      className="inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
    >
      {done ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}{done ? 'Copied' : 'Copy'}
    </button>
  )
}

function IOBlock({ label, text, raw }: { label: string; text: string; raw?: string | null }) {
  const [showRaw, setShowRaw] = useState(false)
  // Only offer "raw" when it actually differs from the compact digest (avoid a pointless toggle).
  const hasRaw = !!raw && raw.trim() !== text.trim()
  const shown = showRaw && raw ? raw : text
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/70">{label}</span>
        <div className="flex items-center gap-1.5">
          {hasRaw && (
            <button
              onClick={() => setShowRaw((v) => !v)}
              className="rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
            >
              {showRaw ? 'Compact' : 'Raw'}
            </button>
          )}
          <CopyButton text={shown} />
        </div>
      </div>
      <pre className="max-h-80 overflow-auto rounded-lg border border-border bg-background/60 p-2.5 text-[11px] leading-relaxed text-foreground/80 whitespace-pre-wrap break-words">
        {shown}
      </pre>
    </div>
  )
}

function StepRow({ step, forceOpen }: { step: TraceStep; forceOpen: boolean }) {
  const [open, setOpen] = useState(false)
  const isOpen = open || forceOpen
  const meta = CAT_META[step.category]
  const Icon = meta.icon
  const hasIO = !!(step.input || step.output)
  return (
    <div className="rounded-lg border border-border bg-panel/30">
      <button
        onClick={() => hasIO && setOpen((v) => !v)}
        className={cn('flex w-full items-center gap-2.5 px-3 py-2 text-left', hasIO && 'hover:bg-panel/60')}
      >
        {hasIO
          ? <ChevronRight className={cn('h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform', isOpen && 'rotate-90')} />
          : <span className="w-3.5 shrink-0" />}
        <span className={cn('inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium', meta.cls)}>
          <Icon className="h-3 w-3" />{meta.label}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm text-foreground/90">{step.summary}</span>
        {step.level && step.level !== 'DEFAULT' && (
          <span
            title={step.status_message ?? undefined}
            className={cn(
              'text-[10px] font-medium',
              step.level === 'ERROR' ? 'text-rose-400' : step.level === 'PAUSED' ? 'text-sky-400' : 'text-amber-400',
            )}
          >
            {step.level}
          </span>
        )}
        {step.tokens ? <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{step.tokens} tok</span> : null}
        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{fmtMs(step.latency)}</span>
      </button>
      {isOpen && hasIO && (
        <div className="space-y-2.5 border-t border-border px-3 py-2.5">
          {step.status_message && (
            <p className={cn('text-[11px]', step.level === 'ERROR' ? 'text-rose-400' : 'text-muted-foreground')}>
              {step.status_message}
            </p>
          )}
          {step.model && <p className="text-[11px] text-muted-foreground">model: <span className="font-mono">{step.model}</span></p>}
          {step.input && <IOBlock label="input" text={step.input} raw={step.raw_input} />}
          {step.output && <IOBlock label="output" text={step.output} raw={step.raw_output} />}
        </div>
      )}
    </div>
  )
}

function TraceDetailView({ id }: { id: string }) {
  const { data, isLoading } = useTrace(id)
  const [showInternal, setShowInternal] = useState(false)
  const [expandAll, setExpandAll] = useState(false)

  if (isLoading) {
    return (
      <div className="space-y-2 p-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading the agent&apos;s steps from Langfuse…
        </div>
        {[0, 1, 2].map((i) => <div key={i} className="h-9 animate-pulse rounded-lg bg-panel/40" />)}
      </div>
    )
  }
  if (!data) return null

  const steps = showInternal ? data.steps : data.steps.filter((s) => s.category !== 'plumbing')
  const hiddenCount = data.steps.length - steps.length

  return (
    <div className="space-y-3 p-3">
      {/* conversation summary */}
      <div className="grid gap-2 sm:grid-cols-2">
        {data.user_message && (
          <div className="rounded-lg border border-border bg-background/50 p-2.5">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/70"><User className="h-3 w-3" /> user</div>
            <p className="text-xs text-foreground/85 line-clamp-4 whitespace-pre-wrap">{data.user_message}</p>
          </div>
        )}
        {data.assistant_reply && (
          <div className="rounded-lg border border-border bg-background/50 p-2.5">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/70"><Bot className="h-3 w-3" /> assistant</div>
            <p className="text-xs text-foreground/85 line-clamp-4 whitespace-pre-wrap">{data.assistant_reply}</p>
          </div>
        )}
      </div>

      {/* controls */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">{steps.length} steps</span>
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => setExpandAll((v) => !v)} className="rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground">
            {expandAll ? 'Collapse all' : 'Expand all'}
          </button>
          <button onClick={() => setShowInternal((v) => !v)} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground">
            {showInternal ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            {showInternal ? 'Hide internal' : `Show internal${hiddenCount ? ` (${hiddenCount})` : ''}`}
          </button>
        </div>
      </div>

      {/* steps */}
      <div className="space-y-1.5">
        {steps.map((s) => <StepRow key={s.id} step={s} forceOpen={expandAll} />)}
      </div>
    </div>
  )
}

export function ObservabilityTab() {
  const { data: status, isLoading: statusLoading } = useTraceStatus()
  const { data: tracesData, isLoading: tracesLoading } = useTraces(25)
  // Deep-link support: Studio → "Recent agent activity" links here with ?trace=<id> to open that turn.
  const [openId, setOpenId] = useState<string | null>(
    () => (typeof window === 'undefined' ? null : new URLSearchParams(window.location.search).get('trace')),
  )

  if (statusLoading) {
    return <div className="py-10 text-center text-muted-foreground"><Loader2 className="inline h-5 w-5 animate-spin" /></div>
  }

  if (!status?.enabled) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5" /> Agent tracing</CardTitle>
          <CardDescription>See every step the assistant takes — graph nodes, model calls, and tool calls — with timing.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div className="space-y-1 text-muted-foreground">
              <p className="font-medium text-foreground">Tracing isn&apos;t configured yet.</p>
              <p>Start the bundled Langfuse stack, create a project, and put its keys in <code className="font-mono text-xs">deploy/.env</code> as <code className="font-mono text-xs">LANGFUSE_PUBLIC_KEY</code> / <code className="font-mono text-xs">LANGFUSE_SECRET_KEY</code>, then redeploy the agent. Steps in <code className="font-mono text-xs">deploy/stacks/observability/</code>.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5" /> Agent tracing</CardTitle>
            <CardDescription>Each row is one assistant turn. Expand to see exactly what it did — which tools it called, what each returned, and how long every step took.</CardDescription>
          </div>
          {status.ui_url && (
            <a href={status.ui_url} target="_blank" rel="noreferrer"
               className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-panel/60 hover:text-foreground">
              Open Langfuse <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {tracesLoading ? (
          <div className="py-8 text-center text-muted-foreground"><Loader2 className="inline h-5 w-5 animate-spin" /></div>
        ) : !tracesData?.traces.length ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No traces yet — chat with the assistant and turns will appear here.</p>
        ) : (
          <div className="space-y-2">
            {tracesData.traces.map((t) => {
              const open = openId === t.id
              return (
                <div key={t.id} className="overflow-hidden rounded-xl border border-border">
                  <button
                    onClick={() => setOpenId(open ? null : t.id)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-panel/50"
                  >
                    <ChevronRight className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{t.user_message || t.name || 'agent-turn'}</p>
                      {t.assistant_reply && <p className="mt-0.5 truncate text-xs text-muted-foreground">{t.assistant_reply}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
                      {t.tags?.map((x) => <Badge key={x} variant="secondary" className="text-[10px]">{x}</Badge>)}
                      <span className="inline-flex items-center gap-1 tabular-nums"><Clock className="h-3 w-3" />{fmtMs(t.latency)}</span>
                      <span className="hidden tabular-nums sm:inline">{fmtTime(t.timestamp)}</span>
                    </div>
                  </button>
                  {open && <div className="border-t border-border bg-background/40"><TraceDetailView id={t.id} /></div>}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
