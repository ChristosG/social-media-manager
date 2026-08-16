import type { ApiClient } from '@platform/auth-ui'

export interface Conversation {
  id: string
  title: string
  model?: string
  system_prompt?: string
  created_at: string
  updated_at: string
}

/** A source the assistant grounded a grounded answer / suggestion on, for click-through provenance. */
export interface SourceCitation {
  title: string
  url: string
  kind: string // 'web' | 'facebook' | 'instagram' | … — distinguishes the org's own posts from external sources
  snippet?: string
}

/** Something the assistant durably LEARNED on a turn (written to memory) — drives the honest "Learned"
 * chip, distinct from the routing badge. `pending` means it's quarantined for review (untrusted source). */
export interface LearnedItem {
  kind: string // 'brand_voice' | 'style_rule' | 'banned_topic' | 'content_pillar' | 'cta_pref' | 'fact'
  label: string
  pending?: boolean
}

export interface Message {
  id: string
  conversation_id: string
  role: string
  content: string
  token_count?: number
  attachments?: Attachment[]
  sources?: SourceCitation[] // grounding provenance, persisted server-side (messages.sources)
  reasoning?: string // the model's thinking trace, persisted server-side (messages.reasoning)
  routeReason?: string // why Auto routing chose to think on this turn, persisted (messages.route_reason)
  learned?: LearnedItem[] // preferences/voice/facts saved this turn, persisted (messages.learned)
  created_at: string
  _error?: string // client-only field for failed messages
  // Client-only: stamped onto an assistant message when its turn was bound to a campaign post (the user
  // came in via "Refine in chat"). Drives the "Apply to post" affordance — the proposed caption lives in
  // `content` (refine_campaign_post bakes it in; the backend has no separate draft-caption field). Not persisted.
  postContext?: { post_id?: string; campaign_id?: string }
  // Client-only: the EXACT {post_id, caption} a refine turn proposed (from the `refine_proposal` event). The
  // reliable source for "Apply to post" — independent of parsing the model's (often paraphrased) prose. Not persisted.
  refineProposal?: { post_id: string; caption: string }
}

/** Normalize a message row from the API: the server uses snake_case `route_reason`; the UI uses
 * `routeReason`. (reasoning + sources already match.) */
function normalizeMessage(m: Message & { route_reason?: string }): Message {
  if (m.route_reason && !m.routeReason) return { ...m, routeReason: m.route_reason }
  return m
}

export interface Attachment {
  id: string
  message_id?: string
  filename: string
  original_filename: string
  mime_type: string
  file_size: number
  status: 'pending' | 'processing' | 'ready' | 'error'
  created_at: string
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
}

export interface ConversationDetailResponse {
  conversation: Conversation
  messages: Message[]
  // Campaign/post this chat is bound to ("Edit in chat" / "Refine in chat"), so the UI can keep a persistent
  // "Apply to post" for the bound post. `active_post_caption` is the post's CURRENT caption — compared with
  // the conversation draft to tell whether there are unapplied changes.
  active_post_id?: string | null
  active_campaign_id?: string | null
  active_post_caption?: string | null
}

export const chatApi = {
  listConversations: (api: ApiClient, limit = 50, offset = 0) =>
    api.get<ConversationListResponse>(`/api/v1/chat/conversations?limit=${limit}&offset=${offset}`),

  getConversation: async (api: ApiClient, id: string) => {
    const data = await api.get<ConversationDetailResponse>(`/api/v1/chat/conversations/${id}`)
    return { ...data, messages: (data.messages || []).map(normalizeMessage) }
  },

  createConversation: (api: ApiClient, title?: string, model?: string) =>
    api.post<{ conversation: Conversation }>('/api/v1/chat/conversations', {
      title: title || 'New Conversation',
      model: model || '/models/Qwen3.5-9B',
    }),

  updateConversation: (api: ApiClient, id: string, data: { title?: string; system_prompt?: string; model?: string }) =>
    api.put<{ conversation: Conversation }>(`/api/v1/chat/conversations/${id}`, data),

  deleteConversation: (api: ApiClient, id: string) =>
    api.delete<{ message: string }>(`/api/v1/chat/conversations/${id}`),

  sendMessage: (api: ApiClient, conversationId: string, content: string, attachmentIds?: string[]) =>
    api.post<{ user_message: Message; assistant_message: Message }>(
      `/api/v1/chat/conversations/${conversationId}/messages`,
      { content, attachment_ids: attachmentIds }
    ),

  searchConversations: (api: ApiClient, query: string, limit = 20) =>
    api.get<ConversationListResponse>(`/api/v1/chat/conversations/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  uploadAttachment: async (api: ApiClient, file: File): Promise<Attachment> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<Attachment>('/api/v1/chat/attachments', formData)
  },

  downloadAttachment: (id: string) =>
    `/api/v1/chat/attachments/${id}/download`,
}
