import { QueryClient } from '@tanstack/react-query'
import { ApiRequestError } from '@platform/auth-ui'

let client: QueryClient | null = null

export function getQueryClient() {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30_000,
          retry: (failureCount, error) => {
            // Never retry client errors (4xx) — auth, permission, not-found
            if (error instanceof ApiRequestError && error.status < 500) {
              return false
            }
            // Retry server errors and network failures up to 2 times
            return failureCount < 2
          },
          refetchOnWindowFocus: false,
        },
      },
    })
  }
  return client
}
