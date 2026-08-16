import * as React from 'react'
import { useAuth } from '../auth-context'

interface AuthGuardProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  onUnauthenticated?: () => void
}

function AuthGuard({ children, fallback, onUnauthenticated }: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth()

  React.useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      onUnauthenticated?.()
    }
  }, [isLoading, isAuthenticated, onUnauthenticated])

  if (isLoading) {
    return fallback ?? (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return fallback ?? null
  }

  return <>{children}</>
}

export { AuthGuard }
