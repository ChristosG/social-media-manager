'use client'

import { useRouter } from 'next/navigation'
import { useAuth, useApiClient, AuthGuard, ThemeToggle, MFASetup, Button, Card, CardHeader, CardTitle, CardContent } from '@platform/auth-ui'
import { useEffect, useState } from 'react'
import type { User } from '@platform/auth-ui'

function DashboardContent() {
  const { user, logout } = useAuth()
  const api = useApiClient()
  const [apiUser, setApiUser] = useState<User | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    api.get<{ user: User }>('/api/auth/me')
      .then((res) => setApiUser(res.user))
      .catch((err) => setApiError(err.message))
  }, [api, refreshKey])

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
          <h1 className="text-xl font-bold">Dashboard</h1>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Name</dt>
                <dd>{user?.display_name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Email</dt>
                <dd>{user?.email}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">User ID</dt>
                <dd className="font-mono text-xs">{user?.id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">MFA</dt>
                <dd>{user?.mfa_enabled ? 'Enabled' : 'Disabled'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Member since</dt>
                <dd>{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API Client Test</CardTitle>
          </CardHeader>
          <CardContent>
            {apiError ? (
              <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                {apiError}
              </div>
            ) : apiUser ? (
              <div className="rounded-lg bg-primary/10 p-3 text-sm">
                useApiClient().get(&apos;/api/auth/me&apos;) returned: {apiUser.email}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Loading...</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Two-Factor Authentication</CardTitle>
          </CardHeader>
          <CardContent>
            <MFASetup onComplete={() => setRefreshKey((k) => k + 1)} />
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

export default function Dashboard() {
  const router = useRouter()

  return (
    <AuthGuard onUnauthenticated={() => router.push('/login')}>
      <DashboardContent />
    </AuthGuard>
  )
}
