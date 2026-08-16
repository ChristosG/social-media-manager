'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { AuthGuard, useAuth } from '@platform/auth-ui'
import { ModuleRail } from '@/components/layout/module-rail'
import { ContextualSidebar } from '@/components/layout/contextual-sidebar'
import { Topbar } from '@/components/layout/topbar'
import { MobileNav } from '@/components/layout/mobile-nav'
import { NotificationToaster } from '@/components/layout/notification-toaster'

function AppLayoutInner({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user } = useAuth()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  const isChat = pathname === '/chat' || pathname.startsWith('/chat/')

  // The app rendered successfully — clear the error boundary's one-shot auto-retry guard so a FUTURE
  // transient failure is allowed to self-heal again (the guard only suppresses back-to-back retry loops).
  useEffect(() => {
    try { sessionStorage.removeItem('ss.err.autoretry') } catch { /* ignore */ }
  }, [])

  // Redirect to onboarding if user has no tenant
  useEffect(() => {
    if (user && !user.tenant_id) {
      router.replace('/onboarding')
    }
  }, [user, router])

  if (user && !user.tenant_id) return null

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <NotificationToaster />
      <ModuleRail />
      <ContextualSidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <Topbar
          onMobileMenuToggle={() => setMobileDrawerOpen(prev => !prev)}
          mobileDrawerOpen={mobileDrawerOpen}
          onMobileDrawerClose={() => setMobileDrawerOpen(false)}
        />
        <main className={`flex-1 overflow-auto ${isChat ? '' : 'pb-14 lg:pb-0'}`}>
          {children}
        </main>
      </div>
      <MobileNav />
    </div>
  )
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  return (
    <AuthGuard onUnauthenticated={() => router.push('/login')}>
      <AppLayoutInner>{children}</AppLayoutInner>
    </AuthGuard>
  )
}
