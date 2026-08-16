'use client'
import { useState, useCallback, useEffect, useMemo, useRef, useSyncExternalStore } from 'react'
import { useApiClient } from '@platform/auth-ui'
import { chatApi, type Message, type ConversationDetailResponse } from '@/lib/chat-api'
import { useChatStream, type SendOptions } from '@/contexts/chat-stream-context'

interface UseChatOptions {
  onTitleUpdate?: (title: string) => void
}

// The server returns the persisted role as lowercase 'user'/'assistant'; the live stream uses the proto
// enum 'MESSAGE_ROLE_USER'. Accept both — checking only the enum is why resume-on-reload silently never
// fired (the loaded last message's role was 'user', so the condition was always false).
const isUserRole = (role?: string) => role === 'MESSAGE_ROLE_USER' || role === 'user'

export function useChat(conversationId: string | null, options?: UseChatOptions) {
  const api = useApiClient()
  const stream = useChatStream()
  const [serverMessages, setServerMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [followups, setFollowups] = useState<string[]>([])
  // The campaign post this conversation is bound to ("Refine in chat") + its current caption, so a persistent
  // "Apply to post" affordance can survive follow-up turns (the per-message button scrolls out of reach).
  const [binding, setBinding] = useState<{ postId: string | null; postCaption: string | null }>(
    { postId: null, postCaption: null })

  // Subscribe to stream state changes via useSyncExternalStore
  const streamVersion = useSyncExternalStore(stream.subscribe, stream.getSnapshot, stream.getSnapshot)

  // Get active stream state for this conversation (if any)
  const activeStream = conversationId ? stream.getStreamState(conversationId) : null

  // Keep refs fresh so callbacks/effects don't depend on changing identities
  const onTitleUpdateRef = useRef(options?.onTitleUpdate)
  onTitleUpdateRef.current = options?.onTitleUpdate
  const streamRef = useRef(stream)
  streamRef.current = stream
  const activeStreamRef = useRef(activeStream)
  activeStreamRef.current = activeStream
  useEffect(() => {
    if (activeStream) {
      stream.updateCallbacks({
        onTitleUpdate: (title: string) => onTitleUpdateRef.current?.(title),
        onSync: (msgs: Message[]) => setServerMessages(msgs),
        onFollowups: setFollowups,
      })
    }
  }, [activeStream, stream])

  // Merge server messages with stream state
  const messages = useMemo(() => {
    if (!activeStream) return serverMessages
    if (!activeStream.streaming && activeStream.messages.length === 0) return serverMessages

    // The stream's first message is the optimistic user message (temp-* ID).
    // The server may already have the real version of that message (with a real ID).
    // Deduplicate by finding the last server user message that matches the stream's
    // optimistic content, and excluding it + anything after it (the stream owns the tail).
    const tempUserMsg = activeStream.messages.find(m => m.id?.startsWith('temp-'))
    if (tempUserMsg) {
      // Find the index of the server copy of this message (last user msg with same content)
      let cutIdx = -1
      for (let i = serverMessages.length - 1; i >= 0; i--) {
        if (isUserRole(serverMessages[i].role) &&
            serverMessages[i].content === tempUserMsg.content) {
          cutIdx = i
          break
        }
      }
      const base = cutIdx >= 0 ? serverMessages.slice(0, cutIdx) : serverMessages
      return [...base, ...activeStream.messages]
    }

    // Stream finished (no temp msgs) — deduplicate by real IDs
    const streamMsgIds = new Set(activeStream.messages.map(m => m.id))
    const base = serverMessages.filter(m => !streamMsgIds.has(m.id))
    return [...base, ...activeStream.messages]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverMessages, activeStream, streamVersion])

  // The bound post for the persistent "Apply to post" bar. Prefer the server binding, but fall back to the
  // latest refine turn's proposal — because loadMessages (which reads the binding) runs at mount, BEFORE the
  // first send persists the binding server-side, so binding.postId is briefly stale-null. The refine message
  // carries the post id + proposed caption directly, so it's the reliable immediate source.
  const latestProposal = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const rp = messages[i].refineProposal
      if (rp?.post_id) return rp
    }
    return null
  }, [messages])

  const streaming = activeStream?.streaming ?? false

  // A finished turn may have applied the caption to the bound post itself (the apply_to_post tool when the
  // user says "apply" in chat). Re-fetch the bound post's current caption when streaming ends, so the
  // persistent "Apply to post" bar clears once the post already matches — not just when applied via its button.
  const prevStreamingRef = useRef(streaming)
  useEffect(() => {
    const was = prevStreamingRef.current
    prevStreamingRef.current = streaming
    if (was && !streaming && conversationId) {
      chatApi.getConversation(api, conversationId)
        .then(d => setBinding({ postId: d.active_post_id ?? null, postCaption: d.active_post_caption ?? null }))
        .catch(() => { /* keep the last known binding */ })
    }
  }, [streaming, conversationId, api])

  const streamingContent = activeStream?.streamingContent ?? ''
  const streamingReasoning = activeStream?.streamingReasoning ?? ''
  const statusMessage = activeStream?.statusMessage ?? ''
  const publishProposal = activeStream?.publishProposal ?? null

  // "View campaign" chip target. It must survive (a) the post-done streamRef teardown AND (b) leaving the
  // conversation and coming back / a full reload — so we persist it durably in localStorage keyed by
  // conversation. Seed from storage on conversation change; persist whenever a turn plans a campaign.
  const streamingCampaign = activeStream?.streamingCampaign ?? null
  const [plannedCampaign, setPlannedCampaign] = useState<{ id: string; brief: string } | null>(null)
  const campaignKey = conversationId ? `ss.campaign.${conversationId}` : null
  useEffect(() => {
    if (!campaignKey) { setPlannedCampaign(null); return }
    try {
      const raw = localStorage.getItem(campaignKey)
      setPlannedCampaign(raw ? JSON.parse(raw) : null)
    } catch { setPlannedCampaign(null) }
  }, [campaignKey])
  useEffect(() => {
    if (streamingCampaign && campaignKey) {
      setPlannedCampaign(streamingCampaign)
      try { localStorage.setItem(campaignKey, JSON.stringify(streamingCampaign)) } catch { /* ignore */ }
    }
  }, [streamingCampaign, campaignKey])

  const loadMessages = useCallback(async (): Promise<ConversationDetailResponse | null> => {
    if (!conversationId) return null
    setLoading(true)
    try {
      const data = await chatApi.getConversation(api, conversationId)
      const msgs = data.messages || []
      setServerMessages(msgs)
      setBinding({ postId: data.active_post_id ?? null, postCaption: data.active_post_caption ?? null })

      // Detect if we're resuming after a reload mid-stream:
      // Last message is a user message AND no active WebSocket stream exists
      const lastMsg = msgs[msgs.length - 1]
      if (isUserRole(lastMsg?.role) && !activeStreamRef.current) {
        streamRef.current.resumeStream(conversationId, {
          onTitleUpdate: (title: string) => onTitleUpdateRef.current?.(title),
          onSync: (msgs: Message[]) => setServerMessages(msgs),
          onFollowups: setFollowups,
          onNoActiveStream: () => {
            // Stream already finished server-side between our REST call and resume attempt.
            // Do one more REST fetch as a safety net.
            chatApi.getConversation(api, conversationId)
              .then(freshData => {
                const freshMsgs = freshData.messages || []
                setServerMessages(freshMsgs)
              })
              .catch(() => { /* already have messages from initial load */ })
          },
        })
      }

      return data
    } catch (err) {
      console.error('Failed to load messages', err)
      return null
    } finally {
      setLoading(false)
    }
  }, [api, conversationId])

  const sendMessage = useCallback(async (content: string, attachmentIds?: string[], sendOptions?: SendOptions) => {
    if (!conversationId || !content.trim()) return
    setFollowups([])
    stream.startStream(conversationId, content, attachmentIds, {
      onTitleUpdate: options?.onTitleUpdate,
      onSync: (msgs) => setServerMessages(msgs),
      onFollowups: setFollowups,
    }, sendOptions)
  }, [conversationId, stream, options?.onTitleUpdate])

  const retryMessage = useCallback((messageId: string) => {
    const msg = messages.find(m => m.id === messageId)
    if (!msg) return
    // Remove the failed message from server messages
    setServerMessages(prev => prev.filter(m => m.id !== messageId))
    sendMessage(msg.content)
  }, [messages, sendMessage])

  const stopStreaming = useCallback(() => {
    stream.stopStream()
  }, [stream])

  return {
    messages,
    loading,
    streaming,
    streamingContent,
    streamingReasoning,
    statusMessage,
    followups,
    publishProposal,
    plannedCampaign,
    activePostId: binding.postId ?? latestProposal?.post_id ?? null,
    activePostCaption: binding.postCaption,
    proposedCaption: latestProposal?.caption ?? null,
    resumePublish: stream.resumePublish,
    loadMessages,
    sendMessage,
    retryMessage,
    stopStreaming,
    setMessages: setServerMessages,
  }
}
