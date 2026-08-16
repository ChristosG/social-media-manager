'use client'

import { useState, useEffect, useRef } from 'react'
import { MarkdownRenderer } from './markdown-renderer'
import { cn } from '@/lib/utils'

interface ThinkingBlockProps {
  content: string
  isThinking: boolean
}

export function ThinkingBlock({ content, isThinking }: ThinkingBlockProps) {
  const [expanded, setExpanded] = useState(false)
  const [duration, setDuration] = useState(0)
  const startRef = useRef<number | null>(null)
  const prevThinking = useRef(isThinking)

  // Auto-expand when thinking starts
  useEffect(() => {
    if (isThinking) setExpanded(true)
  }, [isThinking])

  // Auto-collapse when thinking finishes
  useEffect(() => {
    if (prevThinking.current && !isThinking) {
      setExpanded(false)
    }
    prevThinking.current = isThinking
  }, [isThinking])

  // Track thinking duration
  useEffect(() => {
    if (!isThinking) return
    if (startRef.current === null) startRef.current = Date.now()
    const interval = setInterval(() => {
      setDuration(Math.floor((Date.now() - startRef.current!) / 1000))
    }, 100)
    return () => clearInterval(interval)
  }, [isThinking])

  return (
    <div className="mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors py-1"
      >
        {isThinking ? (
          <>
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
            </span>
            <span className="italic">
              Thinking{duration > 0 ? ` (${duration}s)` : '...'}
            </span>
          </>
        ) : (
          <>
            <svg
              className={cn('h-3 w-3 shrink-0 transition-transform duration-200', expanded && 'rotate-90')}
              viewBox="0 0 12 12"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4.5 2l4 4-4 4" />
            </svg>
            <span>
              {duration > 0 ? `Thought for ${duration}s` : 'Thinking'}
            </span>
          </>
        )}
      </button>

      <div
        className={cn(
          'overflow-hidden transition-all duration-300 ease-in-out',
          expanded ? 'max-h-[5000px] opacity-100' : 'max-h-0 opacity-0',
        )}
      >
        <div className="pl-3 border-l-2 border-primary/20 mt-1 text-sm text-muted-foreground">
          <MarkdownRenderer content={content} />
          {isThinking && content.length > 0 && (
            <span className="inline-flex items-center gap-0.5 h-4 ml-0.5 align-middle">
              <span className="w-1 h-1 rounded-full bg-current animate-bounce [animation-delay:0ms]" />
              <span className="w-1 h-1 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
              <span className="w-1 h-1 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
