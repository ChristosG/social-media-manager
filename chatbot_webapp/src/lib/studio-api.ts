import type { ApiClient } from '@platform/auth-ui'

export interface MemoryEntry {
  id: string
  kind: string
  key: string | null
  value: Record<string, unknown>
  source: string
  active: boolean
  pending_review?: boolean
  updated_at: string
}
export interface LedgerPost {
  id: string; title: string; brief: string | null; status: string
  platform: string | null; content: string | null; created_at: string; updated_at: string
  // 'imported' = pulled from a connected account (not created in Social Studio); 'custom' = user-typed draft.
  origin?: string | null; external_post_id?: string | null
}
export interface OrgProfile {
  name?: string | null; mission: string | null; one_liner: string | null; audience: string | null
  regions: string[]; default_platform?: string | null; updated_at: string
}
export interface Program {
  id: string; name: string; description: string | null
  source_url: string | null; updated_at: string
}
export interface Capability {
  id: string
  org_id: string | null
  kind: string
  name: string
  config: Record<string, unknown>
  enabled: boolean
  is_global: boolean
  updated_at: string
}
export interface ResearchResult {
  mission: string
  one_liner: string
  audience: string
  regions: string[]
  programs: { name: string; description: string }[]
  sources: string[]
}
export interface Source {
  id: string
  kind: string
  name: string
  config: { url: string; type?: string; latest_n?: number }
  enabled: boolean
  last_status: 'pending' | 'ok' | 'partial' | 'failed'
  last_error: string | null
  detected_kind: string | null
  feed_url: string | null
  last_refreshed_at: string | null
  created_at: string
  updated_at: string
}
export interface SourceDocument {
  id: string
  url: string
  title: string | null
  author: string | null
  published_at: string | null
  fetched_at: string
  char_count: number | null
}

export interface TraceSummary {
  id: string
  name: string | null
  timestamp: string | null
  latency: number | null
  tokens: number | null
  tags: string[]
  user_message: string | null
  assistant_reply: string | null
}
export type StepCategory = 'llm' | 'tool' | 'node' | 'plumbing'
export interface TraceStep {
  id: string
  name: string
  category: StepCategory
  type: string | null
  latency: number | null
  model: string | null
  tokens: number | null
  level: string | null
  status_message?: string | null   // why the level is non-DEFAULT (error text, or the HITL pause explainer)
  summary: string
  input: string | null   // compact digest (default view)
  output: string | null
  raw_input?: string | null   // full payload, shown on demand
  raw_output?: string | null
}
export interface TraceDetail {
  id: string
  name: string | null
  timestamp: string | null
  latency: number | null
  user_message: string | null
  assistant_reply: string | null
  steps: TraceStep[]
}

const BASE = '/api/v1/agent'

export interface PromptTemplate {
  key: string
  label: string
  description: string
  placeholders: string[]
  default: string
  template: string
  is_overridden: boolean
}

export const promptsApi = {
  list: (api: ApiClient) => api.get<{ prompts: PromptTemplate[] }>(`${BASE}/prompts`),
  save: (api: ApiClient, key: string, template: string) =>
    api.put<{ ok: boolean }>(`${BASE}/prompts/${key}`, { template }),
  reset: (api: ApiClient, key: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/prompts/${key}`),
}

export const observabilityApi = {
  status: (api: ApiClient) =>
    api.get<{ enabled: boolean; ui_url: string }>(`${BASE}/observability/status`),
  listTraces: (api: ApiClient, limit = 20) =>
    api.get<{ enabled: boolean; traces: TraceSummary[] }>(`${BASE}/observability/traces?limit=${limit}`),
  getTrace: (api: ApiClient, id: string) =>
    api.get<TraceDetail>(`${BASE}/observability/traces/${id}`),
}

export const studioApi = {
  listMemory: (api: ApiClient, kind?: string) =>
    api.get<{ entries: MemoryEntry[] }>(`${BASE}/memory${kind ? `?kind=${kind}` : ''}`),
  listPendingMemory: (api: ApiClient) =>
    api.get<{ entries: MemoryEntry[] }>(`${BASE}/memory/pending`),
  approveMemory: (api: ApiClient, id: string) =>
    api.post<{ ok: boolean }>(`${BASE}/memory/${id}/approve`, {}),
  createMemory: (api: ApiClient, body: { kind: string; value: Record<string, unknown>; key?: string }) =>
    api.post<MemoryEntry>(`${BASE}/memory`, body),
  updateMemory: (api: ApiClient, id: string, body: { value?: Record<string, unknown>; active?: boolean }) =>
    api.put<{ ok: boolean }>(`${BASE}/memory/${id}`, body),
  deleteMemory: (api: ApiClient, id: string) =>
    api.delete<{ message: string }>(`${BASE}/memory/${id}`),
  listLedger: (api: ApiClient, status?: string) =>
    api.get<{ posts: LedgerPost[] }>(`${BASE}/ledger${status ? `?status=${status}` : ''}`),
  updateLedgerPost: (api: ApiClient, id: string, body: { status?: string; content?: string; platform?: string }) =>
    api.put<{ ok: boolean }>(`${BASE}/ledger/${id}`, body),
  deleteLedgerPost: (api: ApiClient, id: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/ledger/${id}`),
  getProfile: (api: ApiClient) => api.get<{ profile: OrgProfile | null }>(`${BASE}/profile`),
  putProfile: (api: ApiClient, body: { name?: string; mission?: string; one_liner?: string; audience?: string; regions?: string[]; default_platform?: string }) =>
    api.put<{ profile: OrgProfile }>(`${BASE}/profile`, body),
  listPrograms: (api: ApiClient) => api.get<{ programs: Program[] }>(`${BASE}/programs`),
  createProgram: (api: ApiClient, body: { name: string; description?: string; source_url?: string }) =>
    api.post<{ program: Program }>(`${BASE}/programs`, body),
  updateProgram: (api: ApiClient, id: string, body: { name?: string; description?: string; source_url?: string }) =>
    api.put<{ ok: boolean }>(`${BASE}/programs/${id}`, body),
  deleteProgram: (api: ApiClient, id: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/programs/${id}`),
  listCapabilities: (api: ApiClient, kind?: string) =>
    api.get<{ capabilities: Capability[] }>(`${BASE}/capabilities${kind ? `?kind=${kind}` : ''}`),
  createCapability: (api: ApiClient, body: { kind: string; name: string; config: Record<string, unknown> }) =>
    api.post<Capability>(`${BASE}/capabilities`, body),
  updateCapability: (api: ApiClient, id: string, body: { config?: Record<string, unknown>; enabled?: boolean; name?: string }) =>
    api.put<{ ok: boolean }>(`${BASE}/capabilities/${id}`, body),
  deleteCapability: (api: ApiClient, id: string) =>
    api.delete<{ message: string }>(`${BASE}/capabilities/${id}`),
  researchOrg: (api: ApiClient, body: { website_url: string; org_name: string }) =>
    api.post<ResearchResult>(`${BASE}/research`, body),
}

export interface Connection {
  id: string
  provider: 'facebook' | 'instagram'
  external_id: string
  display_name: string
  status: 'active' | 'needs_reconnect' | 'revoked'
  scopes: string[]
  created_at: string
}

export const socialApi = {
  connections: (api: ApiClient) =>
    api.get<{ connections: Connection[] }>(`${BASE}/social/connections`),
  connect: (api: ApiClient, provider: 'facebook' | 'instagram', opts?: { popup?: boolean }) =>
    api.get<{ authorize_url: string }>(
      `${BASE}/social/connect/${provider}${opts?.popup ? '?popup=1' : ''}`),
  addSource: (api: ApiClient, connectionId: string) =>
    api.post<Source>(`${BASE}/social/connections/${connectionId}/sources`, {}),
  disconnect: (api: ApiClient, connectionId: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/social/connections/${connectionId}`),
}

export interface ScheduledPost {
  id: string
  targets: { provider: string; connection_id: string }[]
  caption: string
  image_ids: string[]
  scheduled_at: string
  status: 'pending' | 'publishing' | 'published' | 'failed' | 'canceled'
  result: Record<string, { permalink?: string; error?: string; status?: string; id?: string }>
  post_id: string | null
}
export interface AppNotification {
  id: string; type: string; title: string; body: string
  link: string | null; read: boolean; created_at: string
}
export interface SocialPost {
  url: string; title: string | null; published_at: string | null
  image_url: string | null; source_name: string
}
export interface PublishRequest {
  targets: string[]; caption: string; image_ids: string[]
  scheduled_at?: string | null; post_id?: string | null; confirm?: boolean
}

export const publishApi = {
  publish: (api: ApiClient, body: PublishRequest) =>
    api.post<ScheduledPost>(`${BASE}/social/publish`, body),
  listScheduled: (api: ApiClient) =>
    api.get<{ items: ScheduledPost[] }>(`${BASE}/social/scheduled`),
  cancelScheduled: (api: ApiClient, id: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/social/scheduled/${id}`),
  listPosts: (api: ApiClient, provider: 'facebook' | 'instagram') =>
    api.get<{ posts: SocialPost[] }>(`${BASE}/social/posts?provider=${provider}`),
  refreshSocials: (
    api: ApiClient,
    body: { provider?: 'facebook' | 'instagram'; force?: boolean },
  ) =>
    api.post<{
      refreshed: { source_id: string; status: string; ingested: number; skipped: number }[]
      skipped_fresh: string[]
    }>(`${BASE}/social/refresh`, body),
}

export interface Comment {
  id: string
  connection_id: string
  provider: 'facebook' | 'instagram'
  external_id: string
  post_external_id: string | null
  scheduled_post_id: string | null
  author_name: string | null
  message: string
  permalink: string | null
  commented_at: string | null
  status: 'open' | 'replied' | 'ignored'
  reply_text: string
  reply_external_id: string | null
  reply_mode: 'draft' | 'auto' | null
  replied_at: string | null
  created_at: string
  /** The parent post this comment is on (when we published it through the app) — for inbox context. */
  post?: { caption: string; image_ids?: string[]; image_url?: string; permalink?: string | null } | null
}
export interface CommentPollResult {
  status: string
  connections?: number
  new?: number
  drafted?: number
  auto_replied?: number
}

export const commentsApi = {
  list: (api: ApiClient, status?: string) =>
    api.get<{ items: Comment[]; can_engage: boolean }>(
      `${BASE}/comments${status ? `?status=${status}` : ''}`),
  getSettings: (api: ApiClient) =>
    api.get<{ auto_reply_safe: boolean; can_engage: boolean }>(`${BASE}/comments/settings`),
  putSettings: (api: ApiClient, auto_reply_safe: boolean) =>
    api.put<{ auto_reply_safe: boolean }>(`${BASE}/comments/settings`, { auto_reply_safe }),
  poll: (api: ApiClient) =>
    api.post<CommentPollResult>(`${BASE}/comments/poll`, {}),
  reply: (api: ApiClient, id: string, text: string) =>
    api.post<Comment>(`${BASE}/comments/${id}/reply`, { text }),
  ignore: (api: ApiClient, id: string) =>
    api.post<{ ok: boolean }>(`${BASE}/comments/${id}/ignore`),
}

export interface CalendarItem {
  /** The ledger post id (stable across the lifecycle). Null for scheduled-only rows with no ledger link. */
  post_id?: string | null
  /** Row id — the scheduled-post id when scheduled, else the post id. Used by the reschedule endpoint. */
  id: string
  when: string
  /** Lifecycle of this single post (the backend deduped — one item per post). */
  stage: LifecycleStage
  title: string
  caption?: string | null
  platform?: string | null
  image_ids?: string[]
  targets?: unknown[]
  permalink?: string | null
  error?: string | null
  /** Present only when the calendar item is campaign-linked — gates inline refine (refine needs campaign authz). */
  campaign_id?: string | null
  /** Tailored refine chips, when the backend surfaces them for this post. */
  refine_suggestions?: string[]
}

export const calendarApi = {
  get: (api: ApiClient, frm: string, to: string, platform?: string) =>
    api.get<{ items: CalendarItem[]; suggested: string[] }>(
      `${BASE}/social/calendar?frm=${frm}&to=${to}${platform ? `&platform=${platform}` : ''}`),
  reschedule: (api: ApiClient, id: string, when: string) =>
    api.patch<{ ok: boolean }>(`${BASE}/social/scheduled/${id}/reschedule`, { when }),
  planDate: (api: ApiClient, postId: string, body: { planned_for?: string | null; planned_at?: string | null }) =>
    api.put<{ ok: boolean }>(`${BASE}/ledger/${postId}/plan`, body),
}

export const notificationsApi = {
  list: (api: ApiClient) =>
    api.get<{ items: AppNotification[]; unread_count: number }>(`${BASE}/notifications`),
  markRead: (api: ApiClient, id: string) =>
    api.post<{ ok: boolean }>(`${BASE}/notifications/${id}/read`),
  markAllRead: (api: ApiClient) =>
    api.post<{ ok: boolean }>(`${BASE}/notifications/read-all`),
}

export interface ConversationDraft {
  caption: string
  images: { id: string; url: string }[]
}

export const conversationsApi = {
  getDraft: (api: ApiClient, conversationId: string) =>
    api.get<{ draft: ConversationDraft | null }>(`${BASE}/conversations/${conversationId}/draft`),
}

export const imagesApi = {
  /** Upload a user-supplied image; the server stores it as an org image and returns a signed URL. */
  upload: (api: ApiClient, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<{ id: string; url: string }>(`${BASE}/images/upload`, fd)
  },
}

/** A single value with its period-over-period change. */
export interface InsightsKpi {
  value: number
  delta_pct: number
}
export interface InsightsKpis {
  reach: InsightsKpi
  engagement: InsightsKpi
  link_clicks: InsightsKpi
  followers: InsightsKpi
  published: InsightsKpi
}
/** One weekly point of the reach/engagement trend. */
export interface InsightsSeriesPoint {
  week: string   // ISO date
  reach: number
  engagement: number
}
/** A leaderboard entry — one of the top-performing posts in the range. */
export interface InsightsTopPost {
  post_id: string
  caption: string
  provider: string
  origin?: string | null
  reach: number
  engagement: number
  link_clicks: number
  permalink?: string | null
}
/** One captured snapshot of a single post's metrics (drill-down growth series). */
export interface PostInsightPoint {
  captured_at: string   // ISO
  reach: number
  engagement: number
  link_clicks: number
}

export type InsightsPlatform = 'all' | 'facebook' | 'instagram'

export interface InsightsSummary {
  kpis?: InsightsKpis
  series?: InsightsSeriesPoint[]
  top_posts?: InsightsTopPost[]
  updated_at?: string | null
  /** Post counts by content pillar over the window (owned data) — drives the mix donut. */
  content_mix?: { pillar: string; count: number }[]
  status_funnel: Record<string, number>
  /** Why reach/engagement is or isn't shown: 'ok' = real numbers; 'no_scope' = needs the insights
   *  permission; 'error' = permission is fine but Meta/the metric failed (don't tell them to reconnect). */
  meta_status?: 'ok' | 'no_scope' | 'error'

  // ---- legacy keys (still returned for backwards-compat; no longer rendered) ----
  posts_per_day?: { day: string; count: number }[]
  learned_count?: number
  comments?: Record<string, number>
  meta_available?: boolean
  meta?: { impressions: number; engagements: number } | null
}

export const insightsApi = {
  summary: (api: ApiClient, platform: InsightsPlatform = 'all', range = 30) =>
    api.get<InsightsSummary>(`${BASE}/insights/summary?platform=${platform}&range=${range}`),
  /** A single post's metric history, oldest→newest. */
  posts: (api: ApiClient, postId: string) =>
    api.get<PostInsightPoint[]>(`${BASE}/insights/posts/${postId}`),
  /** Enqueue a fresh metric pull. Returns whether it was enqueued + the remaining cooldown. */
  refresh: (api: ApiClient) =>
    api.post<{ enqueued: boolean; cooldown_seconds: number }>(`${BASE}/insights/refresh`),
  /** Publish-related org settings (opt-in UTM link tagging). */
  socialSettings: (api: ApiClient) =>
    api.get<{ utm_tagging: boolean }>(`${BASE}/social/settings`),
  setUtm: (api: ApiClient, utm_tagging: boolean) =>
    api.put<{ utm_tagging: boolean }>(`${BASE}/social/settings`, { utm_tagging }),
}

export type LifecycleStage = 'drafting' | 'drafted' | 'approved' | 'scheduled' | 'posted' | 'failed'
export interface PostLifecycle {
  stage: LifecycleStage
  scheduled_at: string | null
  published_at: string | null
  permalink: string | null
  error: string | null
}
export interface CampaignPost {
  id: string
  caption: string | null
  status: string
  planned_at: string | null
  images: { id: string; url: string }[]
  refine_suggestions?: string[]   // tailored refine chips (server-suggested)
}
export interface CampaignSlot {
  id: string
  slot_date: string
  slot_at: string | null   // full date+time when set (preferred over slot_date)
  angle: string
  platform: string | null
  post_id: string | null
  position: number
  post?: CampaignPost | null     // enriched by GET /campaigns/{id}
  lifecycle?: PostLifecycle      // enriched by GET /campaigns/{id}
}
export interface CampaignProgress {
  total: number; drafted: number; approved: number; scheduled: number; posted: number; failed: number
}
export interface Campaign {
  id: string
  brief: string
  platform: string | null
  status: 'proposed' | 'approved' | 'archived'
  fill_status: string | null   // null | 'filling' | 'done' | 'error' — drafting progress (async approve)
  fill_error: string | null
  created_at: string
  slots: CampaignSlot[]
  progress?: CampaignProgress    // enriched by GET /campaigns/{id}
}

export const ledgerApi = {
  setImages: (api: ApiClient, id: string, image_ids: string[]) =>
    api.put<{ ok: boolean }>(`${BASE}/ledger/${id}/images`, { image_ids }),
  generateImage: (api: ApiClient, id: string, prompt?: string) =>
    api.post<{ id: string; url: string }>(`${BASE}/ledger/${id}/images/generate`, { prompt }),
  /** Restore a post's previous caption (server-persisted; 409 if nothing to undo). */
  undo: (api: ApiClient, id: string) =>
    api.post<{ ok: boolean; caption: string }>(`${BASE}/ledger/${id}/undo`, {}),
}
export const campaignsApi = {
  list: (api: ApiClient) => api.get<{ campaigns: Campaign[] }>(`${BASE}/campaigns`),
  get: (api: ApiClient, id: string) => api.get<{ campaign: Campaign }>(`${BASE}/campaigns/${id}`),
  approve: (api: ApiClient, id: string) =>
    api.post<{ status: string; filled?: number; total?: number; message?: string }>(`${BASE}/campaigns/${id}/approve`, {}),
  approvePost: (api: ApiClient, id: string, postId: string) =>
    api.post<{ ok: boolean; status: string }>(`${BASE}/campaigns/${id}/posts/${postId}/approve`, {}),
  approveAllPosts: (api: ApiClient, id: string) =>
    api.post<{ ok: boolean; approved: number }>(`${BASE}/campaigns/${id}/approve-posts`, {}),
  scheduleApproved: (api: ApiClient, id: string) =>
    api.post<{ scheduled: number; skipped: { post_id: string; reason: string }[] }>(
      `${BASE}/campaigns/${id}/schedule-approved`, {}),
  /** Propose a refined caption for a post. This is a PROPOSAL — it does NOT write. */
  refinePost: (api: ApiClient, id: string, postId: string, intent: string) =>
    api.post<{ caption: string; suggestions: string[] }>(
      `${BASE}/campaigns/${id}/posts/${postId}/refine`, { intent }),
  remove: (api: ApiClient, id: string) => api.delete<{ ok: boolean }>(`${BASE}/campaigns/${id}`),
  /** Delete ONE post/slot from a campaign (the per-card trash button). */
  deleteSlot: (api: ApiClient, id: string, slotId: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/campaigns/${id}/slots/${slotId}`),
  /** Add a user-typed custom draft to a campaign; it becomes a normal drafted post with all AI features. */
  addCustomDraft: (api: ApiClient, id: string, body: { caption: string; date?: string; time?: string }) =>
    api.post<{ ok: boolean; slot_id: string; post_id: string }>(`${BASE}/campaigns/${id}/custom-draft`, body),
}

/** Per-source knowledge footprint, keyed by source id. */
export type SourceStats = Record<string, { documents: number; chunks: number }>

export const sourcesApi = {
  list: (api: ApiClient) =>
    api.get<{ sources: Source[] }>(`${BASE}/sources`),
  stats: (api: ApiClient) =>
    api.get<{ stats: SourceStats }>(`${BASE}/sources/stats`),
  create: (api: ApiClient, body: { name: string; url: string; type?: 'auto' | 'single' | 'section' | 'rss'; latest_n?: number }) =>
    api.post<Source>(`${BASE}/sources`, body),
  refresh: (api: ApiClient, id: string) =>
    api.post<{ status: string; ingested: number; skipped: number; failed: number }>(`${BASE}/sources/${id}/refresh`, {}),
  documents: (api: ApiClient, id: string) =>
    api.get<{ documents: SourceDocument[] }>(`${BASE}/sources/${id}/documents`),
  remove: (api: ApiClient, id: string) =>
    api.delete<{ ok: boolean }>(`${BASE}/sources/${id}`),
}
