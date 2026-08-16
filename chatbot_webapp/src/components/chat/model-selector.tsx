'use client'

import { useState, useRef, useEffect } from 'react'
import { icons } from '@/components/icons'
import { cn } from '@/lib/utils'

const MODELS = [
  { id: '/models/Qwen3.5-9B', label: 'Qwen 3.5 9B', provider: 'Local (vLLM)' },
  { id: '/engines2/NVIDIA-Nemotron-Nano-9B-v2-FP8', label: 'Nemotron 9B', provider: 'Local (vLLM)' },
  { id: 'ilsp/Krikri-8b-Instruct', label: 'DeepSeek R1 8B', provider: 'Local (Triton)' },
  { id: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4', provider: 'Anthropic' },
  { id: 'claude-haiku-4-20250414', label: 'Claude Haiku 4', provider: 'Anthropic' },
  { id: 'gpt-4o', label: 'GPT-4o', provider: 'OpenAI' },
  { id: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'OpenAI' },
]

interface ModelSelectorProps {
  value?: string
  onChange: (model: string) => void
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const selected = MODELS.find(m => m.id === value) || MODELS[0]

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-lg border border-transparent px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:border-border hover:bg-accent hover:text-foreground transition-colors"
      >
        <icons.sparkles className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{selected.label}</span>
        <icons.chevronDown className="h-3 w-3" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-popover p-1.5 shadow-[0_18px_60px_-18px_oklch(0_0_0/0.75)] z-50">
          {MODELS.map(model => (
            <button
              key={model.id}
              onClick={() => { onChange(model.id); setOpen(false) }}
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors',
                model.id === selected.id
                  ? 'bg-primary/12 text-foreground'
                  : 'text-popover-foreground hover:bg-accent/70',
              )}
            >
              <div>
                <div className="font-medium">{model.label}</div>
                <div className="text-xs text-muted-foreground">{model.provider}</div>
              </div>
              {model.id === selected.id && <icons.check className="h-4 w-4 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
