import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '@platform/auth-ui'
import { studioApi, sourcesApi, socialApi, observabilityApi, promptsApi, calendarApi, insightsApi, campaignsApi, ledgerApi } from '@/lib/studio-api'
import type { InsightsPlatform } from '@/lib/studio-api'

export function usePrompts() {
  const api = useApiClient()
  return useQuery({ queryKey: ['prompts'], queryFn: () => promptsApi.list(api) })
}
export function useSavePrompt() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { key: string; template: string }) => promptsApi.save(api, a.key, a.template),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompts'] }),
  })
}
export function useResetPrompt() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => promptsApi.reset(api, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompts'] }),
  })
}

export function useTraceStatus() {
  const api = useApiClient()
  return useQuery({ queryKey: ['observability', 'status'], queryFn: () => observabilityApi.status(api) })
}
export function useTraces(limit = 20) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['observability', 'traces', limit],
    queryFn: () => observabilityApi.listTraces(api, limit),
    refetchInterval: 15_000,
    // Keep the current list visible while the 15s poll refetches, so identical results don't flash/
    // re-animate the rows (the "same info cycling" the user saw).
    placeholderData: (prev) => prev,
  })
}
export function useTrace(id: string | null) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['observability', 'trace', id],
    queryFn: () => observabilityApi.getTrace(api, id as string),
    enabled: !!id,
  })
}

export function useMemory(kind?: string) {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'memory', kind ?? 'all'], queryFn: () => studioApi.listMemory(api, kind) })
}
export function usePendingMemory() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'memory', 'pending'], queryFn: () => studioApi.listPendingMemory(api) })
}
export function useApproveMemory() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => studioApi.approveMemory(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'memory'] }),
  })
}
export function useLedger(status?: string) {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'ledger', status ?? 'all'], queryFn: () => studioApi.listLedger(api, status) })
}
export function useUpdateLedger() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; status?: string; content?: string; platform?: string }) =>
      studioApi.updateLedgerPost(api, a.id, { status: a.status, content: a.content, platform: a.platform }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'ledger'] }),
  })
}
export function useDeleteLedger() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => studioApi.deleteLedgerPost(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'ledger'] }),
  })
}
export function useProfile() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'profile'], queryFn: () => studioApi.getProfile(api) })
}
export function useCreateMemory() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { kind: string; value: Record<string, unknown>; key?: string }) => studioApi.createMemory(api, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'memory'] }),
  })
}
export function useUpdateMemory() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; value?: Record<string, unknown>; active?: boolean }) =>
      studioApi.updateMemory(api, a.id, { value: a.value, active: a.active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'memory'] }),
  })
}
export function useDeleteMemory() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => studioApi.deleteMemory(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'memory'] }),
  })
}
export function useUpdateProfile() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { name?: string; mission?: string; one_liner?: string; audience?: string; regions?: string[]; default_platform?: string }) =>
      studioApi.putProfile(api, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'profile'] }),
  })
}
export function usePrograms() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'programs'], queryFn: () => studioApi.listPrograms(api) })
}
export function useCreateProgram() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { name: string; description?: string; source_url?: string }) => studioApi.createProgram(api, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'programs'] }),
  })
}
export function useUpdateProgram() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; name?: string; description?: string; source_url?: string }) =>
      studioApi.updateProgram(api, a.id, { name: a.name, description: a.description, source_url: a.source_url }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'programs'] }),
  })
}
export function useDeleteProgram() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => studioApi.deleteProgram(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'programs'] }),
  })
}
export function useCapabilities(kind?: string) {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'capabilities', kind ?? 'all'], queryFn: () => studioApi.listCapabilities(api, kind) })
}
export function useCreateCapability() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { kind: string; name: string; config: Record<string, unknown> }) => studioApi.createCapability(api, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'capabilities'] }),
  })
}
export function useUpdateCapability() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; config?: Record<string, unknown>; enabled?: boolean; name?: string }) =>
      studioApi.updateCapability(api, a.id, { config: a.config, enabled: a.enabled, name: a.name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'capabilities'] }),
  })
}
export function useDeleteCapability() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => studioApi.deleteCapability(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'capabilities'] }),
  })
}
export function useResearchOrg() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { website_url: string; org_name: string }) => studioApi.researchOrg(api, b),
    // Refresh on BOTH success and error: research_org commits profile + programs in their own transactions
    // BEFORE its slow web-fetch/LLM tail, so even a request timeout usually leaves real data to show.
    // Invalidating on settled means the just-saved org info appears in Studio regardless of the HTTP outcome.
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['studio', 'profile'] })
      qc.invalidateQueries({ queryKey: ['studio', 'memory'] })
      qc.invalidateQueries({ queryKey: ['studio', 'programs'] })
    },
  })
}
export function useSources() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'sources'], queryFn: () => sourcesApi.list(api) })
}
export function useSourceStats() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'sources', 'stats'], queryFn: () => sourcesApi.stats(api) })
}
export function useCreateSource() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: { name: string; url: string; type?: 'auto' | 'single' | 'section' | 'rss'; latest_n?: number }) =>
      sourcesApi.create(api, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'sources'] }),
  })
}
export function useRefreshSource() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => sourcesApi.refresh(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'sources'] }),
  })
}
export function useSourceDocuments(id: string, enabled: boolean) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['studio', 'sources', id, 'documents'],
    queryFn: () => sourcesApi.documents(api, id),
    enabled,
  })
}
export function useDeleteSource() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => sourcesApi.remove(api, id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ['studio', 'sources'] })
      qc.removeQueries({ queryKey: ['studio', 'sources', id, 'documents'] })
    },
  })
}
export function useConnections() {
  const api = useApiClient()
  return useQuery({ queryKey: ['studio', 'connections'], queryFn: () => socialApi.connections(api) })
}
export function useAddConnectionSource() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (connectionId: string) => socialApi.addSource(api, connectionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['studio', 'sources'] })
      qc.invalidateQueries({ queryKey: ['studio', 'connections'] })
    },
  })
}
export function useDisconnect() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (connectionId: string) => socialApi.disconnect(api, connectionId),
    onSuccess: () => {
      // Disconnecting also deletes the connection's bound source(s) server-side, so the sources
      // list is stale too — refresh both (the panel renders sources).
      qc.invalidateQueries({ queryKey: ['studio', 'connections'] })
      qc.invalidateQueries({ queryKey: ['studio', 'sources'] })
    },
  })
}
export function useCalendar(frm: string, to: string, platform?: string) {
  const api = useApiClient()
  return useQuery({ queryKey: ['calendar', frm, to, platform ?? ''], queryFn: () => calendarApi.get(api, frm, to, platform) })
}
export function useReschedule() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({ mutationFn: (a: { id: string; when: string }) => calendarApi.reschedule(api, a.id, a.when),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }) })
}
export function usePlanDate() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { postId: string; planned_for?: string | null; planned_at?: string | null }) =>
      calendarApi.planDate(api, a.postId, { planned_for: a.planned_for, planned_at: a.planned_at }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['campaign'] })   // a campaign post's date may have changed
    },
  })
}

export function useInsights(platform: InsightsPlatform = 'all', range = 30) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['insights', platform, range],
    queryFn: () => insightsApi.summary(api, platform, range),
    // Insights are expensive (a live Meta call) and Meta-rate-limited, and stay fresh via the background
    // poller + the explicit "Refresh" button. So hold the cache for 5 min instead of the global 30s —
    // revisiting the tab shouldn't re-fetch on every visit.
    staleTime: 5 * 60_000,
  })
}
/** A single post's metric history (drill-down growth chart). */
export function usePostInsights(postId: string | null) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['insights', 'post', postId],
    queryFn: () => insightsApi.posts(api, postId as string),
    enabled: !!postId,
  })
}
/** Enqueue a fresh metric pull; invalidates all insights views on success. */
export function useRefreshInsights() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: () => insightsApi.refresh(api),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['insights'] }),
  })
}

export function useSocialSettings() {
  const api = useApiClient()
  return useQuery({ queryKey: ['social-settings'], queryFn: () => insightsApi.socialSettings(api) })
}

export function useSetUtm() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) => insightsApi.setUtm(api, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-settings'] }),
  })
}

export function useCampaigns() {
  const api = useApiClient()
  return useQuery({ queryKey: ['campaigns'], queryFn: () => campaignsApi.list(api) })
}
export function useApproveCampaign() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => campaignsApi.approve(api, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign'] })   // detail view → refetch → see fill_status → poll
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['studio', 'ledger'] })
    },
  })
}
export function useDeleteCampaign() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => campaignsApi.remove(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['campaigns'] }),
  })
}

/** One enriched campaign (slots carry post + lifecycle). Polls every 2s while it's still drafting. */
export function useCampaign(id: string | null) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['campaign', id],
    enabled: !!id,
    queryFn: () => campaignsApi.get(api, id as string),
    refetchInterval: (q) =>
      (q.state.data as { campaign?: { fill_status?: string | null } } | undefined)?.campaign?.fill_status === 'filling'
        ? 2000 : false,
  })
}

function invalidateCampaignViews(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['campaign'] })
  qc.invalidateQueries({ queryKey: ['campaigns'] })
  qc.invalidateQueries({ queryKey: ['calendar'] })
  qc.invalidateQueries({ queryKey: ['studio', 'ledger'] })
}

/** Edit a campaign post's caption (and/or status) — refreshes the detail view, calendar and ledger. */
export function useUpdateCampaignPost() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; content?: string; status?: string }) =>
      studioApi.updateLedgerPost(api, a.id, { content: a.content, status: a.status }),
    onSuccess: () => invalidateCampaignViews(qc),
  })
}

/**
 * Shared invalidator for any post write: refreshes the specific campaign detail AND the calendar.
 * Keys match the real shapes used here — `useCampaign` is ['campaign', id] and `useCalendar` is
 * ['calendar', frm, to, platform]; invalidating ['campaign'] / ['calendar'] (prefix match) covers all.
 */
export function useInvalidatePost() {
  const qc = useQueryClient()
  return (cid: string) => {
    qc.invalidateQueries({ queryKey: ['campaign', cid] })
    qc.invalidateQueries({ queryKey: ['calendar'] })
  }
}

/**
 * Propose a refined caption for a campaign post. Returns { caption, suggestions } — a PROPOSAL.
 * It does NOT auto-write, so there is no invalidation here; the caller shows a diff and Applies.
 */
export function useRefinePost() {
  const api = useApiClient()
  return useMutation({
    mutationFn: (a: { campaignId: string; postId: string; intent: string }) =>
      campaignsApi.refinePost(api, a.campaignId, a.postId, a.intent),
  })
}

/** Undo a post's last caption change (server-persisted). Refreshes the campaign + calendar. */
export function useUndoPost() {
  const api = useApiClient()
  const invalidate = useInvalidatePost()
  return useMutation({
    mutationFn: (a: { campaignId: string; postId: string }) => ledgerApi.undo(api, a.postId),
    onSuccess: (_data, a) => invalidate(a.campaignId),
  })
}

/** Approve ONE drafted campaign post — the review gate before it can be scheduled. */
export function useApproveCampaignPost() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { campaignId: string; postId: string }) =>
      campaignsApi.approvePost(api, a.campaignId, a.postId),
    onSuccess: () => invalidateCampaignViews(qc),
  })
}

/** Approve every drafted post in a campaign in one click. */
export function useApproveAllCampaignPosts() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) => campaignsApi.approveAllPosts(api, campaignId),
    onSuccess: () => invalidateCampaignViews(qc),
  })
}

/** Delete ONE post/slot from a campaign (per-card trash). */
export function useDeleteCampaignSlot() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { campaignId: string; slotId: string }) =>
      campaignsApi.deleteSlot(api, a.campaignId, a.slotId),
    onSuccess: () => { invalidateCampaignViews(qc); qc.invalidateQueries({ queryKey: ['studio', 'ledger'] }) },
  })
}

/** Add a user-typed custom draft to a campaign (it becomes a normal drafted post with all AI features). */
export function useAddCustomDraft() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { campaignId: string; caption: string; date?: string; time?: string }) =>
      campaignsApi.addCustomDraft(api, a.campaignId, { caption: a.caption, date: a.date, time: a.time }),
    onSuccess: () => { invalidateCampaignViews(qc); qc.invalidateQueries({ queryKey: ['studio', 'ledger'] }) },
  })
}

/** Schedule every APPROVED post at its planned date, to the connected account for its platform. */
export function useScheduleApprovedCampaign() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) => campaignsApi.scheduleApproved(api, campaignId),
    onSuccess: () => { invalidateCampaignViews(qc); qc.invalidateQueries({ queryKey: ['scheduled'] }) },
  })
}

/** Replace a post's images (add an uploaded image, or remove one). */
export function useSetPostImages() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; image_ids: string[] }) => ledgerApi.setImages(api, a.id, a.image_ids),
    onSuccess: () => invalidateCampaignViews(qc),
  })
}

/** Generate one image for a post from its caption (or an override prompt). */
export function useGeneratePostImage() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; prompt?: string }) => ledgerApi.generateImage(api, a.id, a.prompt),
    onSuccess: () => invalidateCampaignViews(qc),
  })
}

// Plain async helper — triggers a full-page redirect, not a query
export function useConnectSocial() {
  const api = useApiClient()
  return (provider: 'facebook' | 'instagram', opts?: { popup?: boolean }) =>
    socialApi.connect(api, provider, opts)
}
