'use client'
import { CornerDownRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export function FollowUpChips({ options, onSelect, disabled }: {
  options: string[]
  onSelect: (text: string) => void
  disabled?: boolean
}) {
  if (!options.length) return null
  return (
    <div className="mx-auto w-full max-w-[var(--pau-chat-width)] px-4 pb-3 pt-1">
      <div className="flex flex-wrap gap-2 reveal-stagger">
        {options.map((opt) => (
          <button
            key={opt}
            disabled={disabled}
            onClick={() => onSelect(opt)}
            className={cn(
              'group flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-sm text-foreground transition-all',
              'hover:border-primary/40 hover:text-primary hover:shadow-[0_4px_16px_-8px_var(--pau-glow-primary)]',
              'disabled:opacity-50',
            )}
          >
            <CornerDownRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}
