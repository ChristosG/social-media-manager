import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '@platform/auth-ui'
import { commentsApi } from '@/lib/studio-api'

export function useComments(status?: string) {
  const api = useApiClient()
  return useQuery({
    queryKey: ['comments', status ?? 'all'],
    queryFn: () => commentsApi.list(api, status),
  })
}

export function useCommentSettings() {
  const api = useApiClient()
  return useQuery({ queryKey: ['comments', 'settings'], queryFn: () => commentsApi.getSettings(api) })
}

export function useUpdateCommentSettings() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (autoReplySafe: boolean) => commentsApi.putSettings(api, autoReplySafe),
    // Enabling it can auto-post the safe backlog server-side, so refresh the whole inbox, not just settings.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}

export function usePollComments() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: () => commentsApi.poll(api),
    // A poll can ingest new comments and post auto-replies — refresh the whole inbox.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}

export function useReplyComment() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (a: { id: string; text: string }) => commentsApi.reply(api, a.id, a.text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}

export function useIgnoreComment() {
  const api = useApiClient(); const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => commentsApi.ignore(api, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}
