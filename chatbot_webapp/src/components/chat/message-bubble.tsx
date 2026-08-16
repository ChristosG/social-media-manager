'use client'

import { memo, useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { MarkdownRenderer } from './markdown-renderer'
import { ThinkingBlock } from './thinking-block'
import { MessageAttachments } from './message-attachments'
import { FilePreviewModal } from './file-preview-modal'
import { icons } from '@/components/icons'
import { LogoMark } from '@/components/brand'
import type { Message, Attachment } from '@/lib/chat-api'
import { PostToSocialsChip } from '@/components/publish/post-to-socials-chip'
import { ApplyToPostButton } from './apply-to-post-button'
import { SourceChips } from './source-chips'

interface MessageBubbleProps {
  message: Message
  isStreaming?: boolean
  onRetry?: (messageId: string) => void
}

// Friendly names for the honest "Learned" chip — distinct from the routing badge. This chip means the
// agent actually wrote something to your knowledge this turn (you can edit it in Studio → Knowledge);
// the violet "Thought this through" badge only means the model used thinking tokens on this turn.
const LEARNED_KIND: Record<string, string> = {
  brand_voice: 'Brand voice',
  style_rule: 'Style rule',
  banned_topic: "Won't mention",
  content_pillar: 'Theme',
  cta_pref: 'Call-to-action',
  fact: 'Fact',
}

function isUserRole(role: string) {
  return role === 'MESSAGE_ROLE_USER' || role === 'user'
}

function parseThinking(content: string, isStreaming?: boolean) {
  const idx = content.indexOf('<think>')
  if (idx === -1) return { thinking: null, response: content, isThinking: false }

  const afterTag = content.substring(idx + 7)
  const endIdx = afterTag.indexOf('</think>')

  if (endIdx === -1) {
    // No closing tag — still thinking (if streaming) or truncated
    return { thinking: afterTag, response: '', isThinking: !!isStreaming }
  }

  return {
    thinking: afterTag.substring(0, endIdx),
    response: afterTag.substring(endIdx + 8).replace(/^\n+/, ''),
    isThinking: false,
  }
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = Math.floor((now - then) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export const MessageBubble = memo(function MessageBubble({ message, isStreaming, onRetry }: MessageBubbleProps) {
  const isUser = isUserRole(message.role)
  const [copied, setCopied] = useState(false)
  const [showTimestamp, setShowTimestamp] = useState(false)
  const [previewAttachment, setPreviewAttachment] = useState<Attachment | null>(null)

  const parsed = useMemo(
    () => isUser ? null : parseThinking(message.content, isStreaming),
    [message.content, isStreaming, isUser],
  )

  const handleCopy = async () => {
    const textToCopy = parsed?.response ?? message.content
    await navigator.clipboard.writeText(textToCopy)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isUser) {
    return (
      <div className="flex justify-end animate-message-in" onMouseEnter={() => setShowTimestamp(true)} onMouseLeave={() => setShowTimestamp(false)}>
        <div className="max-w-[80%]">
          {/* Attachment cards above the message text */}
          {message.attachments && message.attachments.length > 0 && (
            <MessageAttachments
              attachments={message.attachments}
              onPreview={setPreviewAttachment}
            />
          )}
          <div className={cn(
            'rounded-2xl rounded-br-md border border-border bg-panel-raised px-4 py-2.5 shadow-[inset_0_1px_0_0_oklch(1_0_0/0.03)]',
            message._error && 'border-destructive'
          )}>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
          {message._error && (
            <div className="flex items-center justify-end gap-2 mt-1">
              <span className="text-xs text-destructive">{message._error}</span>
              {onRetry && (
                <button
                  onClick={() => onRetry(message.id)}
                  className="text-xs text-primary hover:underline font-medium"
                >
                  Retry
                </button>
              )}
            </div>
          )}
          {!message._error && !message.id?.startsWith('temp-') && (
            <p className={cn(
              'text-[10px] text-muted-foreground text-right mt-0.5 transition-opacity',
              showTimestamp ? 'opacity-100' : 'opacity-0',
            )}>{formatRelativeTime(message.created_at)}</p>
          )}
        </div>
        {previewAttachment && (
          <FilePreviewModal
            attachment={previewAttachment}
            onClose={() => setPreviewAttachment(null)}
          />
        )}
      </div>
    )
  }

  return (
    <div className="group flex gap-2 sm:gap-3 animate-message-in" onMouseEnter={() => setShowTimestamp(true)} onMouseLeave={() => setShowTimestamp(false)}>
      {/* Assistant mark */}
      <LogoMark className="flex-shrink-0 h-7 w-7 mt-0.5 rounded-lg" glyphClassName="h-[48%] w-[48%]" />


      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Auto-routing hint: the assistant chose to think harder on this turn (NOT a memory write) */}
        {message.routeReason && (
          <div className="mb-1 inline-flex items-center gap-1 rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-300">
            <icons.sparkles className="h-3 w-3" /> Thought this through · {message.routeReason}
          </div>
        )}
        {/* Honest "Learned" signal: a preference/voice/fact was actually saved to your knowledge this turn.
            Distinct from the routing badge above — green = saved, amber = pending your review in Studio. */}
        {message.learned && message.learned.length > 0 && (
          <div className="mb-1 flex flex-wrap gap-1">
            {message.learned.map((l, i) => (
              <div
                key={`${l.kind}-${i}`}
                title={`${l.pending ? 'Pending your review' : 'Saved to your knowledge'} — ${LEARNED_KIND[l.kind] ?? 'preference'}: ${l.label} (edit in Studio → Knowledge)`}
                className={cn(
                  'inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium',
                  l.pending
                    ? 'border-amber/30 bg-amber/10 text-amber'
                    : 'border-sage/30 bg-sage/12 text-sage',
                )}
              >
                {l.pending
                  ? <icons.sparkles className="h-3 w-3 shrink-0" />
                  : <icons.check className="h-3 w-3 shrink-0" />}
                <span className="truncate">
                  {l.pending ? 'Pending review' : 'Learned'} · {LEARNED_KIND[l.kind] ?? 'preference'}
                  {l.label ? <span className="opacity-80">: {l.label}</span> : null}
                </span>
              </div>
            ))}
          </div>
        )}
        {/* Reasoning trace delivered as a separate stream (vLLM reasoning_content) */}
        {message.reasoning ? (
          <ThinkingBlock
            content={message.reasoning}
            isThinking={!!isStreaming && !message.content}
          />
        ) : null}
        <div className="text-sm prose-sm">
          {parsed?.thinking !== null && parsed ? (
            <>
              <ThinkingBlock content={parsed.thinking} isThinking={parsed.isThinking} />
              {parsed.response ? (
                <MarkdownRenderer content={parsed.response} />
              ) : !parsed.isThinking && isStreaming ? (
                <span className="inline-flex items-center gap-1 h-5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:300ms]" />
                </span>
              ) : null}
            </>
          ) : (
            <>
              <MarkdownRenderer content={message.content} />
              {isStreaming && message.content === '' && (
                <span className="inline-flex items-center gap-1 h-5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber animate-bounce [animation-delay:300ms]" />
                </span>
              )}
            </>
          )}
        </div>

        {/* Grounding provenance — where this answer / these suggestions came from */}
        <SourceChips sources={message.sources} />

        {/* Campaign refine write-back: this turn proposed a refined caption for a bound post. Prefer the
            structured proposal (reliable) and fall back to the legacy postContext+prose path. Always visible
            (the primary CTA for a refine turn) — not hover-gated. */}
        {!isStreaming && message.content && (message.refineProposal?.post_id || message.postContext?.post_id) && (
          <div className="mt-2">
            <ApplyToPostButton
              postContext={{
                post_id: message.refineProposal?.post_id || message.postContext!.post_id!,
                campaign_id: message.postContext?.campaign_id,
              }}
              markdown={message.content}
              proposedCaption={message.refineProposal?.caption}
            />
          </div>
        )}

        {/* Hover actions */}
        {!isStreaming && message.content && (
          <div className="mt-1 opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity flex items-center gap-2 flex-wrap">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              aria-label="Copy message"
            >
              {copied ? (
                <><icons.check className="h-3 w-3" /> Copied</>
              ) : (
                <><icons.copy className="h-3 w-3" /> Copy</>
              )}
            </button>
            <PostToSocialsChip markdown={message.content} conversationId={message.conversation_id} />
            {showTimestamp && !message.id?.startsWith('streaming') && (
              <span className="text-[10px] text-muted-foreground">{formatRelativeTime(message.created_at)}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
})
