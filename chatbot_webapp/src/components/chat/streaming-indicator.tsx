'use client'

import { icons } from '@/components/icons'

interface StreamingIndicatorProps {
  onStop: () => void
}

export function StreamingIndicator({ onStop }: StreamingIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-2 py-2">
      <button
        onClick={onStop}
        className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      >
        <icons.squareStop className="h-3 w-3" />
        Stop generating
      </button>
    </div>
  )
}
