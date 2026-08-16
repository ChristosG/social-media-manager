'use client'

import { useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Megaphone, Pencil } from 'lucide-react'
import { useApiClient } from '@platform/auth-ui'
import { ChatInput } from './chat-input'
import { ModelSelector } from './model-selector'
import { LogoMark } from '@/components/brand'
import { useFileAttachments } from '@/hooks/use-file-attachments'
import { chatApi } from '@/lib/chat-api'

interface EmptyStateProps {
  onNewChat: (title?: string, model?: string) => Promise<{ id: string }>
}

// Concrete things an NPO marketer can do — clicking one auto-sends it, so each must map to a real
// capability: suggest_posts, plan_campaign (→ review in Workspace → Campaigns), draft_post,
// answer_about_org, list_ledger. (Calendar/Insights are screens you browse, not chat asks.)
const STARTERS = [
  { emoji: '✨', text: 'Suggest 3 post ideas for us' },
  { emoji: '📣', text: 'Plan a 2-week campaign to boost donations' },
  { emoji: '📅', text: 'What should we post this week?' },
  { emoji: '✍️', text: 'Draft an Instagram post about an upcoming event' },
  { emoji: '📊', text: 'What programs does our organization run?' },
  { emoji: '🗂️', text: "Which posts have we worked on, and what's their status?" },
]

export function EmptyState({ onNewChat }: EmptyStateProps) {
  const router = useRouter()
  const api = useApiClient()
  const [model, setModel] = useState('/models/Qwen3.5-9B')
  const attachments = useFileAttachments()

  // A prefill handed off from the Workspace ("Open/Refine in chat"). Read in an effect (not during render)
  // so SSR and the client agree, then seed the composer once.
  const [seed, setSeed] = useState<string | undefined>(undefined)
  // The campaign post this chat opened to refine ("Refine in chat"). Consumed like `pending-compose`
  // (read once, removeItem) and attached to ONLY the first send so refine_campaign_post is bound to it.
  const [postContext, setPostContext] = useState<{ post_id?: string; campaign_id?: string } | undefined>(undefined)
  // A human-readable description of what this chat is bound to, for the landing card ('campaign' | 'post').
  const [binding, setBinding] = useState<{ kind: 'campaign' | 'post'; label: string } | undefined>(undefined)
  useEffect(() => {
    try {
      const c = sessionStorage.getItem('pending-compose')
      if (c) { sessionStorage.removeItem('pending-compose'); setSeed(c) }
    } catch { /* ignore */ }
    try {
      const ctx = sessionStorage.getItem('pending-context')
      if (ctx) {
        sessionStorage.removeItem('pending-context')
        const parsed = JSON.parse(ctx) as { postId?: string; campaignId?: string; kind?: 'campaign' | 'post'; label?: string }
        // Bind when EITHER a post (per-post refine) OR a campaign (campaign-level "Edit in chat") is given.
        if (parsed?.postId || parsed?.campaignId) {
          setPostContext({ post_id: parsed.postId, campaign_id: parsed.campaignId })
          const kind = parsed.kind ?? (parsed.postId ? 'post' : 'campaign')
          setBinding({ kind, label: parsed.label || (kind === 'post' ? 'this post' : 'this campaign') })
        }
      }
    } catch { /* ignore */ }
  }, [])

  const handleAddFiles = useCallback((newFiles: File[]) => {
    attachments.addFiles(newFiles, (file) => chatApi.uploadAttachment(api, file))
  }, [api, attachments])

  const handleSend = async (
    content: string,
    opts?: { groundSources?: boolean; reasoning?: boolean; webSearch?: boolean },
  ) => {
    try {
      // Resolve any uploads started in this composer before we navigate away.
      let attachmentIds: string[] | undefined
      if (attachments.hasFiles) {
        try { attachmentIds = await attachments.waitForUploads() } catch { /* send without files */ }
      }
      attachments.clearAll()
      const conv = await onNewChat(undefined, model)
      // Hand the message (attachment ids + composer toggles + any campaign-post binding) to ChatArea to
      // send over the WebSocket. postContext rides only this first send (it's consumed here, one-shot).
      sessionStorage.setItem('pending-message', JSON.stringify({
        conversationId: conv.id,
        content,
        attachmentIds: attachmentIds?.length ? attachmentIds : undefined,
        sendOptions: postContext ? { ...opts, postContext } : opts,
      }))
      router.push(`/chat/${conv.id}`)
    } catch (err) {
      console.error('Failed to create conversation', err)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex-1 flex flex-col items-center justify-center px-4 overflow-hidden">
        {/* Ambient warm wash */}
        <div className="pointer-events-none absolute inset-0 bg-ambient" />

        <div className="relative z-10 flex flex-col items-center reveal-stagger w-full">
          <LogoMark className="h-16 w-16 mb-6" glyphClassName="h-[50%] w-[50%]" />

          {binding ? (
            <>
              <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                {binding.kind === 'campaign' ? <Megaphone className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
                {binding.kind === 'campaign' ? 'Editing campaign' : 'Refining post'}
              </div>
              <h1 className="max-w-xl font-display text-2xl sm:text-3xl font-semibold leading-tight tracking-tight text-center text-foreground">
                {binding.label}
              </h1>
              <p className="mt-3 text-sm sm:text-base text-muted-foreground text-center max-w-md leading-relaxed">
                {binding.kind === 'campaign'
                  ? 'I’m working on this campaign. Tell me what to change — add a post, move a date, or remove one.'
                  : 'I’m working on this post. Tell me how to change the caption and I’ll propose an update to apply.'}
              </p>
            </>
          ) : (
            <>
              <h1 className="font-display text-3xl sm:text-[2.75rem] font-semibold leading-[1.05] tracking-tight text-center text-foreground">
                What should we <span className="text-gradient-warm">post</span>?
              </h1>

              <p className="mt-3 text-sm sm:text-base text-muted-foreground text-center max-w-md leading-relaxed">
                Your nonprofit&apos;s social-media studio. Ask for post ideas, draft for any platform,
                or get answers about your org — grounded in your mission.
              </p>

              <div className="mt-7 grid w-full max-w-xl gap-2.5 sm:grid-cols-2">
                {STARTERS.map((s) => (
                  <button
                    key={s.text}
                    onClick={() => handleSend(s.text)}
                    className="group flex items-center gap-3 rounded-xl border border-border bg-card/80 px-4 py-3 text-left text-sm text-foreground transition-all hover:border-primary/40 hover:bg-accent hover:shadow-[0_8px_30px_-12px_var(--pau-glow-primary)]"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-base transition-colors group-hover:bg-primary/20">
                      {s.emoji}
                    </span>
                    <span className="leading-snug">{s.text}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="mt-7">
            <ModelSelector value={model} onChange={setModel} />
          </div>
        </div>
      </div>
      <ChatInput
        onSend={handleSend}
        files={attachments.files}
        onAddFiles={handleAddFiles}
        onRemoveFile={attachments.removeFile}
        initialValue={seed}
      />
    </div>
  )
}
