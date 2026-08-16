'use client'

import { useRouter } from 'next/navigation'
import { AuthGuard } from '@platform/auth-ui'
import { AppShell } from '@/components/app-shell'

export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()

  return (
    <AuthGuard onUnauthenticated={() => router.push('/login')}>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  )
}
