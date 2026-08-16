import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '@platform/auth-ui'
import { publishApi, conversationsApi, type PublishRequest, type ScheduledPost } from '@/lib/studio-api'

export function usePublishPost() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: PublishRequest) => publishApi.publish(api, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['studio', 'scheduled'] })
      qc.invalidateQueries({ queryKey: ['studio', 'notifications'] })
      qc.invalidateQueries({ queryKey: ['studio', 'connections'] })
    },
  })
}

export function useScheduled() {
  const api = useApiClient()
  return useQuery({
    queryKey: ['studio', 'scheduled'],
    queryFn: () => publishApi.listScheduled(api),
    refetchInterval: (query) => {
      const items: ScheduledPost[] = query.state.data?.items ?? []
      const hasActive = items.some((p) => p.status === 'pending' || p.status === 'publishing')
      return hasActive ? 20000 : false
    },
  })
}

export function useCancelScheduled() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => publishApi.cancelScheduled(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'scheduled'] }),
  })
}

export function useSocialPosts(provider: 'facebook' | 'instagram') {
  const api = useApiClient()
  return useQuery({
    queryKey: ['studio', 'social-posts', provider],
    queryFn: () => publishApi.listPosts(api, provider),
    enabled: !!provider,
  })
}

export function useRefreshSocials() {
  const api = useApiClient()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { provider?: 'facebook' | 'instagram'; force?: boolean }) =>
      publishApi.refreshSocials(api, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'social-posts'] }),
  })
}

export function useConversationDraft(conversationId: string | undefined) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['studio', 'conversation-draft', conversationId],
    queryFn: () => conversationsApi.getDraft(api, conversationId as string),
    enabled: !!conversationId,
    staleTime: 0,
  })
}
