'use client'

import { createContext, useContext, useRef, useCallback, useMemo, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useApiClient, useWSClient } from '@platform/auth-ui'
import { chatApi, type Message, type SourceCitation, type LearnedItem } from '@/lib/chat-api'

/** The browser's IANA timezone (e.g. "America/Los_Angeles"), or '' if the runtime doesn't expose one. */
function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch {
    return ''
  }
}

/** The publish approval gate's preview, surfaced when the agent's publish_post tool interrupts. */
export interface PublishProposal {
  kind: 'publish_proposal'
  caption: string
  image_ids: string[]
  images?: { id: string; url: string }[]   // signed display URLs for the preview
  platform?: string
  targets: { id: string; provider: string; display_name: string }[]
}
/** The user's decision sent back to resume the paused graph. */
export interface PublishDecision {
  approved: boolean
  caption?: string
  image_ids?: string[]
  targets?: string[]
  scheduled_at?: string | null
}

interface StreamState {
  conversationId: string
  messages: Message[]
  streaming: boolean
  streamingContent: string
  streamingReasoning: string
  streamingSources: SourceCitation[]
  streamingRoute: string
  streamingLearned: LearnedItem[]
  streamingCampaign: { id: string; brief: string } | null
  refineProposal: { post_id: string; caption: string } | null
  publishProposal: PublishProposal | null
  statusMessage: string
  socket: WebSocket | null
}

interface StartStreamCallbacks {
  onTitleUpdate?: (title: string) => void
  onSync?: (messages: Message[]) => void
  onFollowups?: (followups: string[]) => void
}

/** Extra per-send options forwarded into the WebSocket payload. */
export interface SendOptions {
  /** When true the backend should search connected sources and cite them. */
  groundSources?: boolean
  /** When true, enable the model's thinking trace (streamed as `reasoning` events). */
  reasoning?: boolean
  /** When true, expose the public-web search tool for this turn. */
  webSearch?: boolean
  /** Binds THIS turn to a campaign post ("Refine in chat") and/or a campaign ("Edit in chat"). Sent as
   *  `post_context`; the backend reads `post_context.post_id` (scopes refine_campaign_post) and
   *  `post_context.campaign_id` (scopes the campaign-edit tools). One-shot — only the bound turn carries it. */
  postContext?: { post_id?: string; campaign_id?: string }
}

interface ResumeStreamCallbacks extends StartStreamCallbacks {
  onNoActiveStream?: () => void
}

interface ChatStreamContextValue {
  getStreamState: (conversationId: string) => StreamState | null
  startStream: (
    conversationId: string,
    content: string,
    attachmentIds?: string[],
    callbacks?: StartStreamCallbacks,
    sendOptions?: SendOptions,
  ) => void
  resumeStream: (conversationId?: string, callbacks?: ResumeStreamCallbacks) => void
  resumePublish: (decision: PublishDecision) => void
  stopStream: () => void
  // Update callbacks on the active stream (e.g. after remount)
  updateCallbacks: (callbacks: StartStreamCallbacks) => void
  subscribe: (listener: () => void) => () => void
  getSnapshot: () => number // version counter for useSyncExternalStore
}

/** Re-attach client-only fields (thinking trace, auto-routing hint) onto the canonical server messages
 * after the post-`done` background sync — otherwise they'd be wiped, since they aren't persisted. */
function preserveClientFields(serverMsgs: Message[], finished?: Message): Message[] {
  if (!finished?.id) return serverMsgs
  return serverMsgs.map(m => m.id === finished.id
    ? {
        ...m,
        reasoning: m.reasoning ?? finished.reasoning,
        routeReason: m.routeReason ?? finished.routeReason,
        sources: m.sources?.length ? m.sources : finished.sources,
        learned: m.learned?.length ? m.learned : finished.learned,
        // Campaign-post binding is client-only (the server doesn't echo it) — carry it across the sync so
        // "Apply to post" survives the post-`done` refetch while the user stays on the page.
        postContext: m.postContext ?? finished.postContext,
        refineProposal: m.refineProposal ?? finished.refineProposal,
      }
    : m)
}

const ChatStreamContext = createContext<ChatStreamContextValue | null>(null)

export function useChatStream() {
  const ctx = useContext(ChatStreamContext)
  if (!ctx) throw new Error('useChatStream must be used within ChatStreamProvider')
  return ctx
}

export function ChatStreamProvider({ children }: { children: ReactNode }) {
  const wsClient = useWSClient()
  const api = useApiClient()
  const apiRef = useRef(api)
  apiRef.current = api
  const queryClient = useQueryClient()
  const qcRef = useRef(queryClient)
  qcRef.current = queryClient

  // A finished turn may have written a fresh draft (new/edited caption from draft_post, newly
  // generated images). The conversation-draft query has staleTime:0 but nothing remounts it while
  // the user stays on the page, so without an explicit invalidation "Post to socials" would keep
  // serving the FIRST draft it fetched. Re-fetch it on every completed turn.
  const invalidateDraft = useCallback((conversationId: string) => {
    qcRef.current.invalidateQueries({ queryKey: ['studio', 'conversation-draft', conversationId] })
  }, [])

  const streamRef = useRef<StreamState | null>(null)
  const listenersRef = useRef<Set<() => void>>(new Set())
  const versionRef = useRef(0)
  const callbacksRef = useRef<StartStreamCallbacks>({})

  const notify = useCallback(() => {
    versionRef.current += 1
    listenersRef.current.forEach(l => l())
  }, [])

  const getStreamState = useCallback((conversationId: string): StreamState | null => {
    const s = streamRef.current
    if (s && s.conversationId === conversationId) return s
    return null
  }, [])

  const resumePublish = useCallback((decision: PublishDecision) => {
    // Approve or cancel the publish gate → resume the SAME paused turn over the open socket.
    const s = streamRef.current
    if (!s?.socket || !s.publishProposal) return
    s.publishProposal = null
    s.streaming = true
    s.streamingContent = ''
    notify()
    if (s.socket.readyState === WebSocket.OPEN) {
      s.socket.send(JSON.stringify({ action: 'resume_publish', conversation_id: s.conversationId, decision }))
    }
  }, [notify])

  const stopStream = useCallback(() => {
    const s = streamRef.current
    if (!s) return

    if (s.socket) {
      // Tell the backend to cancel upstream LLM generation
      if (s.socket.readyState === WebSocket.OPEN) {
        s.socket.send(JSON.stringify({ action: 'stop', conversation_id: s.conversationId }))
      }
      s.socket.close()
      s.socket = null
    }

    if (s.streamingContent) {
      // Save partial message
      const partialMsg: Message = {
        id: 'partial-' + Date.now(),
        conversation_id: s.conversationId,
        role: 'MESSAGE_ROLE_ASSISTANT',
        content: s.streamingContent,
        reasoning: s.streamingReasoning || undefined,
        created_at: new Date().toISOString(),
      }
      s.messages = [...s.messages, partialMsg]
    }

    s.streaming = false
    s.streamingContent = ''
    s.streamingReasoning = ''
    notify()
  }, [notify])

  const startStream = useCallback(async (
    conversationId: string,
    content: string,
    attachmentIds?: string[],
    callbacks?: StartStreamCallbacks,
    sendOptions?: SendOptions,
  ) => {
    // Close any existing stream
    if (streamRef.current?.socket) {
      streamRef.current.socket.close()
    }

    callbacksRef.current = callbacks || {}

    // This turn may be bound to a campaign post ("Refine in chat"). Stamp the resulting assistant message
    // with it so the UI can offer "Apply to post" only for refine turns. One-shot: it lives in this closure,
    // so it never leaks onto later turns.
    const turnPostContext = sendOptions?.postContext?.post_id ? sendOptions.postContext : undefined

    const tempUserMsg: Message = {
      id: 'temp-' + Date.now(),
      conversation_id: conversationId,
      role: 'MESSAGE_ROLE_USER',
      content,
      created_at: new Date().toISOString(),
    }

    // Initialize stream state
    const state: StreamState = {
      conversationId,
      messages: [tempUserMsg],
      streaming: true,
      streamingContent: '',
      streamingReasoning: '',
      streamingSources: [],
      streamingRoute: '',
      streamingLearned: [],
      streamingCampaign: null,
      refineProposal: null,
      publishProposal: null,
      statusMessage: '',
      socket: null,
    }
    streamRef.current = state
    notify()

    try {
      const { socket } = await wsClient.connect('/ws/chat')
      // If stream was stopped/replaced while connecting, bail
      if (streamRef.current !== state) {
        socket.close()
        return
      }
      state.socket = socket
      notify()

      socket.onmessage = (e) => {
        // If this stream was replaced, ignore stale messages
        if (streamRef.current !== state) return

        const data = JSON.parse(e.data)
        if (data.type === 'token') {
          state.streamingContent += data.data
          notify()
        } else if (data.type === 'reasoning') {
          state.streamingReasoning += data.data
          notify()
        } else if (data.type === 'sources') {
          // Provenance chips for this turn (own posts / cited web sources), emitted just before `done`.
          state.streamingSources = Array.isArray(data.data) ? data.data : []
          notify()
        } else if (data.type === 'route') {
          // Auto routing chose to think this turn — keep the reason for a small UI hint.
          state.streamingRoute = data.data?.reason || ''
          notify()
        } else if (data.type === 'memory_saved') {
          // The agent durably learned a preference/voice/fact this turn — show the honest "Learned" chip.
          state.streamingLearned = Array.isArray(data.data) ? data.data : []
          notify()
        } else if (data.type === 'campaign_planned') {
          // The agent planned a campaign this turn — surface a "View campaign" jump chip (conversation-scoped
          // stream state, so a message refetch can't wipe it).
          state.streamingCampaign = data.data?.id ? data.data : null
          notify()
        } else if (data.type === 'refine_proposal') {
          // The exact post + proposed caption from refine_campaign_post — the reliable basis for "Apply to post".
          state.refineProposal = data.data?.post_id ? data.data : null
          notify()
        } else if (data.type === 'publish_proposal') {
          // HITL gate: the agent paused for publish approval. Finalize any pre-gate narration into a
          // message, stop the spinner, and surface the proposal — but KEEP the socket so the approval
          // can resume the same paused turn. (Don't null streamRef: resume events must still flow.)
          if (state.streamingContent.trim()) {
            state.messages = state.messages.filter(m => !m.id?.startsWith('temp-'))
            state.messages = [...state.messages, {
              id: 'streamed-' + Date.now(), conversation_id: state.conversationId,
              role: 'MESSAGE_ROLE_ASSISTANT', content: state.streamingContent,
              created_at: new Date().toISOString(),
            }]
          }
          state.streamingContent = ''
          state.streaming = false
          state.publishProposal = data.data
          notify()
        } else if (data.type === 'done') {
          state.streaming = false
          state.socket = null
          socket.close()

          const assistantMsg: Message | undefined = data.message
          if (assistantMsg) {
            // The thinking trace isn't persisted server-side — keep it on the live message object.
            if (state.streamingReasoning) assistantMsg.reasoning = state.streamingReasoning
            if (!assistantMsg.sources?.length && state.streamingSources.length) assistantMsg.sources = state.streamingSources
            if (state.streamingRoute) assistantMsg.routeReason = state.streamingRoute
            if (!assistantMsg.learned?.length && state.streamingLearned.length) assistantMsg.learned = state.streamingLearned
            // Stamp the campaign-post binding (client-only) so the UI can offer "Apply to post".
            if (turnPostContext) assistantMsg.postContext = turnPostContext
            // ...and the exact refine proposal, so "Apply to post" is reliable even if the model paraphrased.
            if (state.refineProposal) assistantMsg.refineProposal = state.refineProposal
            state.messages = state.messages.filter(m => !m.id?.startsWith('temp-'))
            state.messages = [...state.messages, assistantMsg]
          } else {
            const fallbackMsg: Message = {
              id: 'streamed-' + Date.now(),
              conversation_id: conversationId,
              role: 'MESSAGE_ROLE_ASSISTANT',
              content: state.streamingContent,
              reasoning: state.streamingReasoning || undefined,
              sources: state.streamingSources.length ? state.streamingSources : undefined,
              routeReason: state.streamingRoute || undefined,
              learned: state.streamingLearned.length ? state.streamingLearned : undefined,
              postContext: turnPostContext,
              refineProposal: state.refineProposal || undefined,
              created_at: new Date().toISOString(),
            }
            state.messages = [...state.messages, fallbackMsg]
          }
          state.streamingContent = ''
          state.streamingReasoning = ''
          state.streamingSources = []
          state.streamingRoute = ''
          state.streamingLearned = []
          // NOTE: streamingCampaign is intentionally NOT reset here — it persists after `done` so the
          // "View campaign" chip stays until the next turn starts (the init block clears it).
          notify()
          callbacksRef.current.onFollowups?.(Array.isArray(data.followups) ? data.followups : [])
          invalidateDraft(conversationId)

          // Background sync for canonical data, then clear the stream. Preserve client-only fields
          // (reasoning trace, auto-routing hint) on the matching message so they don't flicker away.
          const finishedMsg = assistantMsg
          chatApi.getConversation(apiRef.current, conversationId)
            .then(convData => {
              if (streamRef.current === state) {
                const msgs = preserveClientFields(convData.messages || [], finishedMsg)
                callbacksRef.current.onSync?.(msgs)
                streamRef.current = null
                notify()
              }
            })
            .catch(() => {
              if (streamRef.current === state) {
                streamRef.current = null
                notify()
              }
            })
        } else if (data.type === 'status') {
          state.statusMessage = data.data || ''
          notify()
        } else if (data.type === 'title_update') {
          callbacksRef.current.onTitleUpdate?.(data.title)
        } else if (data.type === 'error') {
          console.error('Stream error:', data.data)
          state.streaming = false
          state.streamingContent = ''
          state.statusMessage = ''
          state.socket = null
          socket.close()
          state.messages = state.messages.map(m =>
            m.id === tempUserMsg.id ? { ...m, _error: data.data || 'Stream error' } : m
          )
          notify()
        }
      }

      socket.onerror = () => {
        if (streamRef.current !== state) return
        state.streaming = false
        state.streamingContent = ''
        state.messages = state.messages.map(m =>
          m.id === tempUserMsg.id ? { ...m, _error: 'Connection error' } : m
        )
        notify()
      }

      socket.onclose = () => {
        if (streamRef.current === state) {
          state.socket = null
        }
      }

      const payload = JSON.stringify({
        action: 'send',
        conversation_id: conversationId,
        content,
        // Ground the assistant in the user's LOCAL date (campaign dates, "this week", "today") rather than
        // UTC. Best-effort: omit gracefully if the browser doesn't expose a resolved tz.
        ...(browserTimezone() ? { timezone: browserTimezone() } : {}),
        ...(attachmentIds?.length ? { attachment_ids: attachmentIds } : {}),
        ...(sendOptions?.groundSources !== undefined ? { ground_sources: sendOptions.groundSources } : {}),
        // reasoning is tri-state: true/false = explicit; undefined = Auto (omit → backend router decides).
        ...(sendOptions?.reasoning !== undefined ? { reasoning: sendOptions.reasoning } : {}),
        ...(sendOptions?.webSearch ? { web_search: true } : {}),
        // Bind this turn to the opened post and/or campaign — the backend reads post_context.post_id
        // (refine_campaign_post) and post_context.campaign_id (the campaign-edit tools).
        ...((sendOptions?.postContext?.post_id || sendOptions?.postContext?.campaign_id)
          ? { post_context: sendOptions.postContext } : {}),
      })

      if (socket.readyState === WebSocket.OPEN) {
        socket.send(payload)
      } else {
        socket.addEventListener('open', () => {
          socket.send(payload)
        }, { once: true })
      }
    } catch (err) {
      console.error('WebSocket connection failed, falling back to REST', err)
      if (streamRef.current !== state) return

      try {
        const data = await chatApi.sendMessage(apiRef.current, conversationId, content, attachmentIds)
        state.messages = state.messages.filter(m => !m.id?.startsWith('temp-'))
        state.messages = [...state.messages, data.user_message, data.assistant_message]
      } catch (restErr) {
        console.error('REST fallback failed', restErr)
        state.messages = state.messages.map(m =>
          m.id === tempUserMsg.id ? { ...m, _error: 'Failed to send message' } : m
        )
      }
      state.streaming = false
      state.streamingContent = ''
      notify()
    }
  }, [wsClient, notify, invalidateDraft])

  const resumeStream = useCallback(async (conversationId?: string, callbacks?: ResumeStreamCallbacks) => {
    // Close any existing stream socket
    if (streamRef.current?.socket) {
      streamRef.current.socket.close()
    }

    if (callbacks) {
      callbacksRef.current = { ...callbacksRef.current, ...callbacks }
    }

    try {
      const { socket } = await wsClient.connect('/ws/chat')

      let state: StreamState | null = null

      socket.onmessage = (e) => {
        const data = JSON.parse(e.data)

        if (data.type === 'no_active_stream') {
          socket.close()
          callbacks?.onNoActiveStream?.()
          return
        }

        if (data.type === 'resume_replay') {
          // Initialize stream state from the replay
          state = {
            conversationId: data.conversation_id,
            messages: [],
            streaming: true,
            streamingContent: data.content || '',
            streamingReasoning: data.reasoning || '',
            streamingSources: [],
            streamingRoute: '',
            streamingLearned: [],
            streamingCampaign: null,
            refineProposal: null,
            publishProposal: null,
            statusMessage: '',
            socket,
          }
          streamRef.current = state
          notify()
          return
        }

        // After resume_replay, handle normal streaming events
        if (!state || streamRef.current !== state) return

        if (data.type === 'token') {
          state.streamingContent += data.data
          notify()
        } else if (data.type === 'reasoning') {
          state.streamingReasoning += data.data
          notify()
        } else if (data.type === 'sources') {
          state.streamingSources = Array.isArray(data.data) ? data.data : []
          notify()
        } else if (data.type === 'route') {
          state.streamingRoute = data.data?.reason || ''
          notify()
        } else if (data.type === 'memory_saved') {
          state.streamingLearned = Array.isArray(data.data) ? data.data : []
          notify()
        } else if (data.type === 'campaign_planned') {
          state.streamingCampaign = data.data?.id ? data.data : null
          notify()
        } else if (data.type === 'refine_proposal') {
          // The exact post + proposed caption from refine_campaign_post — the reliable basis for "Apply to post".
          state.refineProposal = data.data?.post_id ? data.data : null
          notify()
        } else if (data.type === 'publish_proposal') {
          if (state.streamingContent.trim()) {
            state.messages = [...state.messages, {
              id: 'streamed-' + Date.now(), conversation_id: state.conversationId,
              role: 'MESSAGE_ROLE_ASSISTANT', content: state.streamingContent,
              created_at: new Date().toISOString(),
            }]
          }
          state.streamingContent = ''
          state.streaming = false
          state.publishProposal = data.data
          notify()
        } else if (data.type === 'done') {
          state.streaming = false
          state.socket = null
          socket.close()

          const assistantMsg: Message | undefined = data.message
          if (assistantMsg) {
            if (state.streamingReasoning) assistantMsg.reasoning = state.streamingReasoning
            if (!assistantMsg.sources?.length && state.streamingSources.length) assistantMsg.sources = state.streamingSources
            if (state.streamingRoute) assistantMsg.routeReason = state.streamingRoute
            if (!assistantMsg.learned?.length && state.streamingLearned.length) assistantMsg.learned = state.streamingLearned
            if (state.refineProposal) assistantMsg.refineProposal = state.refineProposal
            state.messages = [...state.messages, assistantMsg]
          } else {
            const fallbackMsg: Message = {
              id: 'streamed-' + Date.now(),
              conversation_id: state.conversationId,
              role: 'MESSAGE_ROLE_ASSISTANT',
              content: state.streamingContent,
              reasoning: state.streamingReasoning || undefined,
              sources: state.streamingSources.length ? state.streamingSources : undefined,
              routeReason: state.streamingRoute || undefined,
              learned: state.streamingLearned.length ? state.streamingLearned : undefined,
              refineProposal: state.refineProposal || undefined,
              created_at: new Date().toISOString(),
            }
            state.messages = [...state.messages, fallbackMsg]
          }
          state.streamingContent = ''
          state.streamingReasoning = ''
          state.streamingSources = []
          state.streamingRoute = ''
          state.streamingLearned = []
          // NOTE: streamingCampaign is intentionally NOT reset here — it persists after `done` so the
          // "View campaign" chip stays until the next turn starts (the init block clears it).
          notify()
          callbacksRef.current.onFollowups?.(Array.isArray(data.followups) ? data.followups : [])
          invalidateDraft(state.conversationId)

          // Background sync (preserve client-only reasoning/route hint on the matching message)
          const convId = state.conversationId
          const finishedMsg = assistantMsg
          chatApi.getConversation(apiRef.current, convId)
            .then(convData => {
              if (streamRef.current === state) {
                const msgs = preserveClientFields(convData.messages || [], finishedMsg)
                callbacksRef.current.onSync?.(msgs)
                streamRef.current = null
                notify()
              }
            })
            .catch(() => {
              if (streamRef.current === state) {
                streamRef.current = null
                notify()
              }
            })
        } else if (data.type === 'title_update') {
          callbacksRef.current.onTitleUpdate?.(data.title)
        } else if (data.type === 'error') {
          console.error('Resume stream error:', data.data)
          if (state) {
            state.streaming = false
            state.streamingContent = ''
            state.socket = null
          }
          socket.close()
          notify()
        }
      }

      socket.onerror = () => {
        if (state && streamRef.current === state) {
          state.streaming = false
          state.streamingContent = ''
          notify()
        }
        callbacks?.onNoActiveStream?.()
      }

      socket.onclose = () => {
        if (state && streamRef.current === state) {
          state.socket = null
        }
      }

      // Send resume action once connected — pass the conversation id so the server resumes THIS
      // conversation's in-flight generation (not just whatever was the user's most recent one).
      const sendResume = () => {
        socket.send(JSON.stringify({ action: 'resume', ...(conversationId ? { conversation_id: conversationId } : {}) }))
      }

      if (socket.readyState === WebSocket.OPEN) {
        sendResume()
      } else {
        socket.addEventListener('open', sendResume, { once: true })
      }
    } catch (err) {
      console.error('WebSocket connection failed during resume', err)
      callbacks?.onNoActiveStream?.()
    }
  }, [wsClient, notify, invalidateDraft])

  const updateCallbacks = useCallback((callbacks: StartStreamCallbacks) => {
    callbacksRef.current = { ...callbacksRef.current, ...callbacks }
  }, [])

  const subscribe = useCallback((listener: () => void) => {
    listenersRef.current.add(listener)
    return () => { listenersRef.current.delete(listener) }
  }, [])

  const getSnapshot = useCallback(() => versionRef.current, [])

  const value = useMemo<ChatStreamContextValue>(() => ({
    getStreamState,
    startStream,
    resumeStream,
    resumePublish,
    stopStream,
    updateCallbacks,
    subscribe,
    getSnapshot,
  }), [getStreamState, startStream, resumeStream, resumePublish, stopStream, updateCallbacks, subscribe, getSnapshot])

  return (
    <ChatStreamContext.Provider value={value}>
      {children}
    </ChatStreamContext.Provider>
  )
}
