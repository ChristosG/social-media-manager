'use client'

import { Info } from 'lucide-react'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/* -------------------------------------------------------------------------- */
/*  Metric tooltip — a small ⓘ that explains a KPI in one plain-language line. */
/* -------------------------------------------------------------------------- */

export function MetricTooltip({ text, className }: { text: string; className?: string }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label="What does this mean?"
            className={cn(
              'grid h-4 w-4 place-items-center rounded-full text-muted-foreground/50 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              className,
            )}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-[15rem] text-pretty leading-snug">{text}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
