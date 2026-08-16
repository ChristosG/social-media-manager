'use client'

import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MetricTooltip } from './metric-tooltip'

/* -------------------------------------------------------------------------- */
/*  KPI trend card                                                             */
/*                                                                             */
/*  One metric: big value, a ▲/▼ delta vs the previous period, an ⓘ tooltip,   */
/*  and an optional tiny sparkline.                                            */
/* -------------------------------------------------------------------------- */

function Delta({ pct }: { pct: number }) {
  // 0 (or missing) → a neutral em-dash. Up is good (sage), down is muted (not alarming).
  if (!pct || Math.abs(pct) < 0.05) {
    return <span className="text-xs font-medium text-muted-foreground/60 tabular-nums">—</span>
  }
  const up = pct > 0
  const rounded = Math.abs(pct) >= 10 ? Math.round(Math.abs(pct)) : Math.abs(pct).toFixed(1)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums',
        up ? 'text-sage' : 'text-muted-foreground',
      )}
    >
      <span aria-hidden>{up ? '▲' : '▼'}</span>
      {rounded}%
    </span>
  )
}

/** Minimal inline sparkline — a normalised polyline, no axes. */
function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null
  const w = 64
  const h = 20
  const max = Math.max(...points)
  const min = Math.min(...points)
  const span = max - min || 1
  const step = w / (points.length - 1)
  const d = points
    .map((v, i) => {
      const x = i * step
      const y = h - ((v - min) / span) * h
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className="shrink-0 overflow-visible text-primary/70"
      aria-hidden
    >
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function KpiCard({
  label,
  value,
  deltaPct,
  tooltip,
  spark,
  Icon,
}: {
  label: string
  value: number
  deltaPct: number
  tooltip: string
  spark?: number[]
  Icon?: React.ElementType
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 px-4 py-4">
        <div className="flex items-center gap-1.5">
          {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground/70" />}
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
          <MetricTooltip text={tooltip} className="ml-auto" />
        </div>
        <div className="flex items-end justify-between gap-2">
          <div className="min-w-0">
            <p className="text-2xl font-bold leading-none tabular-nums text-foreground">
              {value.toLocaleString()}
            </p>
            <div className="mt-1.5">
              <Delta pct={deltaPct} />
            </div>
          </div>
          {spark && spark.length >= 2 && <Sparkline points={spark} />}
        </div>
      </CardContent>
    </Card>
  )
}
