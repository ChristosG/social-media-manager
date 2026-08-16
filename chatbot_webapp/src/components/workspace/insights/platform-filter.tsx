'use client'

import { Facebook, Instagram, Linkedin } from 'lucide-react'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { InsightsPlatform } from '@/lib/studio-api'

/* -------------------------------------------------------------------------- */
/*  Platform filter — segmented control                                        */
/*                                                                             */
/*  All · Facebook · Instagram are live and drive the `platform` query param.  */
/*  LinkedIn renders disabled with a "soon" hint (future-proofing the API,     */
/*  which is closed to third parties today).                                   */
/* -------------------------------------------------------------------------- */

interface Segment {
  id: InsightsPlatform | 'linkedin'
  label: string
  Icon?: React.ElementType
  disabled?: boolean
}

const SEGMENTS: Segment[] = [
  { id: 'all', label: 'All' },
  { id: 'facebook', label: 'Facebook', Icon: Facebook },
  { id: 'instagram', label: 'Instagram', Icon: Instagram },
  { id: 'linkedin', label: 'LinkedIn', Icon: Linkedin, disabled: true },
]

export function PlatformFilter({
  value,
  onChange,
}: {
  value: InsightsPlatform
  onChange: (p: InsightsPlatform) => void
}) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-1 rounded-xl border border-border bg-panel p-1">
        {SEGMENTS.map(({ id, label, Icon, disabled }) => {
          const active = !disabled && value === id
          const button = (
            <button
              key={id}
              type="button"
              disabled={disabled}
              onClick={() => !disabled && onChange(id as InsightsPlatform)}
              aria-label={label}
              aria-pressed={active}
              className={cn(
                'flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium transition-all',
                active
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : disabled
                    ? 'cursor-not-allowed text-muted-foreground/40'
                    : 'text-muted-foreground hover:bg-panel-raised hover:text-foreground',
              )}
            >
              {Icon && <Icon className="h-3.5 w-3.5" />}
              <span>{label}</span>
            </button>
          )
          // Wrap the disabled LinkedIn segment so the hint is discoverable on hover.
          // (Disabled buttons don't fire pointer events, so the span is the trigger.)
          if (disabled) {
            return (
              <Tooltip key={id}>
                <TooltipTrigger asChild>
                  <span className="inline-flex">{button}</span>
                </TooltipTrigger>
                <TooltipContent>LinkedIn insights — coming soon</TooltipContent>
              </Tooltip>
            )
          }
          return button
        })}
      </div>
    </TooltipProvider>
  )
}
