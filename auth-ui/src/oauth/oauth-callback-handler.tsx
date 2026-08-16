import * as React from 'react'
import { useAuth } from '../auth-context'
import { setAccessToken } from '../token-manager'

interface OAuthCallbackHandlerProps {
  provider: string
  apiUrl?: string
  onSuccess?: (isNewUser: boolean) => void
  onError?: (error: string) => void
}

function OAuthCallbackHandler({
  provider,
  apiUrl = '/api/auth',
  onSuccess,
  onError,
}: OAuthCallbackHandlerProps) {
  const { refreshSession } = useAuth()
  const [error, setError] = React.useState<string | null>(null)
  const processedRef = React.useRef(false)

  React.useEffect(() => {
    if (processedRef.current) return
    processedRef.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    const errorParam = params.get('error')

    if (errorParam) {
      const msg = `OAuth error: ${errorParam}`
      setError(msg)
      onError?.(msg)
      return
    }

    if (!code || !state) {
      const msg = 'Missing OAuth callback parameters'
      setError(msg)
      onError?.(msg)
      return
    }

    ;(async () => {
      try {
        const res = await fetch(
          `${apiUrl}/oauth/${provider}/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
          { credentials: 'include' },
        )
        const data = await res.json()

        if (!res.ok) {
          const msg = data.message || data.error || 'OAuth callback failed'
          setError(msg)
          onError?.(msg)
          return
        }

        if (data.access_token) {
          setAccessToken(data.access_token)
          // Trigger a refresh to establish the session properly
          await refreshSession()
          onSuccess?.(data.is_new_user ?? false)
        }
      } catch {
        const msg = 'Failed to complete OAuth sign-in'
        setError(msg)
        onError?.(msg)
      }
    })()
  }, [provider, apiUrl, onSuccess, onError, refreshSession])

  if (error) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="rounded-lg bg-destructive/10 p-6 text-center">
          <p className="text-sm font-medium text-destructive">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="space-y-4 text-center">
        <div className="h-8 w-8 mx-auto animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Completing sign-in...</p>
      </div>
    </div>
  )
}

export { OAuthCallbackHandler }
