import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '@platform/auth-ui'
import { notificationsApi } from '@/lib/studio-api'

export function useNotifications() {
  const api = useApiClient()
  return useQuery({
    queryKey: ['studio', 'notifications'],
    queryFn: () => notificationsApi.list(api),
    refetchInterval: 45000,
    refetchOnWindowFocus: true,
  })
}

export function useMarkNotificationRead() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'notifications'] }),
  })
}

export function useMarkAllNotificationsRead() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(api),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio', 'notifications'] }),
  })
}
