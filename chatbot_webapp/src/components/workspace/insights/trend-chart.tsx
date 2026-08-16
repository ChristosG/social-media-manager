'use client'

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

/* -------------------------------------------------------------------------- */
/*  Trend chart — a small two-series area chart on the warm Sanctuary palette. */
/*                                                                             */
/*  Used for the panel's reach & engagement weekly trend and (single-series)   */
/*  for a post's growth drill-down. Colours come from the registered           */
/*  --color-chart-* tokens so it stays on-theme in light/dark.                 */
/* -------------------------------------------------------------------------- */

export interface TrendDatum {
  label: string
  reach?: number
  engagement?: number
}

const REACH = 'var(--color-chart-1)'        // coral
const ENGAGEMENT = 'var(--color-chart-3)'    // sage

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { name?: string; value?: number; color?: string }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-2.5 py-1.5 text-xs shadow-[0_12px_40px_-12px_oklch(0_0_0/0.7)]">
      <p className="mb-1 font-medium text-popover-foreground">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5 text-popover-foreground/80">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="capitalize">{p.name}</span>
          <span className="ml-auto font-semibold tabular-nums">{(p.value ?? 0).toLocaleString()}</span>
        </p>
      ))}
    </div>
  )
}

export function TrendChart({
  data,
  series = ['reach', 'engagement'],
  height = 180,
}: {
  data: TrendDatum[]
  series?: ('reach' | 'engagement')[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id="grad-reach" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={REACH} stopOpacity={0.28} />
            <stop offset="100%" stopColor={REACH} stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="grad-engagement" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ENGAGEMENT} stopOpacity={0.28} />
            <stop offset="100%" stopColor={ENGAGEMENT} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={16}
        />
        <YAxis
          tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          width={40}
          allowDecimals={false}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--color-border)' }} />
        {series.includes('reach') && (
          <Area
            type="monotone"
            dataKey="reach"
            name="reach"
            stroke={REACH}
            strokeWidth={2}
            fill="url(#grad-reach)"
            dot={false}
            isAnimationActive={false}
          />
        )}
        {series.includes('engagement') && (
          <Area
            type="monotone"
            dataKey="engagement"
            name="engagement"
            stroke={ENGAGEMENT}
            strokeWidth={2}
            fill="url(#grad-engagement)"
            dot={false}
            isAnimationActive={false}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  )
}
