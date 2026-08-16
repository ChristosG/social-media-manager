'use client'
import { useRef, useEffect, useState, useCallback } from 'react'
import { MessageBubble } from './message-bubble'
import type { Message } from '@/lib/chat-api'
import { icons } from '@/components/icons'

interface MessageListProps {
  messages: Message[]
  loading: boolean
  streamingContent?: string
  streamingReasoning?: string
  statusMessage?: string
  onRetry?: (messageId: string) => void
}

export function MessageList({ messages, loading, streamingContent, streamingReasoning, statusMessage, onRetry }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [showScrollBtn, setShowScrollBtn] = useState(false)

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Auto-scroll on new messages/streaming
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    // Only auto-scroll if near bottom
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (nearBottom) {
      scrollToBottom()
    }
  }, [messages, streamingContent, streamingReasoning, scrollToBottom])

  // Track scroll position for "scroll to bottom" button
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onScroll = () => {
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      setShowScrollBtn(distFromBottom > 200)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <icons.loader className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto scrollbar-thin relative">
      <div className="max-w-[var(--pau-chat-width)] mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4 sm:space-y-6">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onRetry={onRetry} />
        ))}

        {/* Tool-status card while the agent works */}
        {statusMessage && (
          <div className="flex w-fit items-center gap-2.5 rounded-full border border-border bg-card px-3.5 py-2 text-sm">
            <icons.loader className="h-4 w-4 animate-spin text-amber" />
            <span className="shimmer-text font-medium">{statusMessage}</span>
          </div>
        )}

        {streamingContent !== undefined && (
          <MessageBubble
            message={{
              id: 'streaming',
              conversation_id: '',
              role: 'MESSAGE_ROLE_ASSISTANT',
              content: streamingContent || '',
              reasoning: streamingReasoning || undefined,
              created_at: new Date().toISOString(),
            }}
            isStreaming
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          className="sticky bottom-4 left-1/2 -translate-x-1/2 flex items-center justify-center h-9 w-9 rounded-full border border-border bg-card/90 backdrop-blur shadow-[0_8px_30px_-8px_oklch(0_0_0/0.6)] text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors z-10"
          aria-label="Scroll to bottom"
        >
          <icons.arrowDown className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
