import * as React from 'react'
import { useAuth } from '../auth-context'

interface GuestGuardProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  onAuthenticated?: () => void
}

function GuestGuard({ children, fallback, onAuthenticated }: GuestGuardProps) {
  const { isAuthenticated, isLoading } = useAuth()

  React.useEffect(() => {
    if (!isLoading && isAuthenticated) {
      onAuthenticated?.()
    }
  }, [isLoading, isAuthenticated, onAuthenticated])

  if (isLoading) {
    return fallback ?? (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (isAuthenticated) {
    return fallback ?? null
  }

  return <>{children}</>
}

export { GuestGuard }
