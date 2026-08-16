'use client'

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { PieChart as PieIcon } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

/* -------------------------------------------------------------------------- */
/*  Content mix — a small donut of post counts by content pillar.              */
/*                                                                             */
/*  Owned data (no Meta dependency): "what kinds of things are we posting?".   */
/*  Colours cycle the registered --color-chart-* Sanctuary tokens so it stays  */
/*  on-theme in light/dark — no random hex. A gentle hint nudges balance when  */
/*  one pillar dominates the mix.                                              */
/* -------------------------------------------------------------------------- */

export interface ContentMixDatum {
  pillar: string
  count: number
}

// Cycle the five registered chart tokens (primary / amber / sage / coral / magenta).
const SLICE_TOKENS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
] as const

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function MixTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean
  payload?: { name?: string; value?: number; payload?: { fill?: string } }[]
  total: number
}) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  const value = p.value ?? 0
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="rounded-lg border border-border bg-popover px-2.5 py-1.5 text-xs shadow-[0_12px_40px_-12px_oklch(0_0_0/0.7)]">
      <p className="flex items-center gap-1.5 text-popover-foreground/80">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: p.payload?.fill }}
        />
        <span className="capitalize">{p.name}</span>
        <span className="ml-auto font-semibold tabular-nums text-popover-foreground">
          {value.toLocaleString()} · {pct}%
        </span>
      </p>
    </div>
  )
}

export function ContentMix({ data }: { data?: ContentMixDatum[] }) {
  // Guard: nothing to show without at least one categorised post.
  const mix = (data ?? []).filter((d) => d.count > 0)
  const total = mix.reduce((sum, d) => sum + d.count, 0)
  if (mix.length === 0 || total === 0) return null

  const slices = mix.map((d, i) => ({ ...d, fill: SLICE_TOKENS[i % SLICE_TOKENS.length] }))

  // Gentle balance hint when one pillar owns more than half the mix.
  const top = slices[0]
  const second = slices[1]
  const dominant = top && top.count / total > 0.5 ? top : null

  return (
    <Card>
      <CardHeader className="px-5 pb-2 pt-5">
        <div className="flex items-center gap-2">
          <PieIcon className="h-4 w-4 text-primary" />
          <h3 className="font-display text-sm font-semibold tracking-tight text-foreground">
            Content mix (30d)
          </h3>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">Posts by content pillar</p>
      </CardHeader>
      <CardContent className="px-5 pb-5">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
          <div className="h-[148px] w-[148px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="count"
                  nameKey="pillar"
                  cx="50%"
                  cy="50%"
                  innerRadius={42}
                  outerRadius={66}
                  paddingAngle={2}
                  stroke="var(--color-card)"
                  strokeWidth={2}
                  isAnimationActive={false}
                >
                  {slices.map((s) => (
                    <Cell key={s.pillar} fill={s.fill} />
                  ))}
                </Pie>
                <Tooltip content={<MixTooltip total={total} />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend: pillar + count + percent */}
          <ul className="min-w-0 flex-1 space-y-1.5 self-stretch">
            {slices.map((s) => {
              const pct = Math.round((s.count / total) * 100)
              return (
                <li key={s.pillar} className="flex items-center gap-2 text-xs">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: s.fill }}
                  />
                  <span className="min-w-0 flex-1 truncate capitalize text-foreground/90">
                    {s.pillar}
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {s.count.toLocaleString()} · {pct}%
                  </span>
                </li>
              )
            })}
          </ul>
        </div>

        {dominant && (
          <p className="mt-3 text-xs text-muted-foreground">
            Heavy on <span className="font-medium capitalize text-foreground/80">{dominant.pillar}</span>
            {second ? (
              <>
                {' '}— mix in a{' '}
                <span className="font-medium capitalize text-foreground/80">{second.pillar}</span> next.
              </>
            ) : (
              <> — try mixing in another pillar next.</>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
