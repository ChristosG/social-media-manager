'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@platform/auth-ui'
import { ThemeToggle } from '@platform/auth-ui'
import { cn } from '@/lib/utils'
import { Logo, LogoMark } from '@/components/brand'
import { NotificationBell } from '@/components/layout/notification-bell'
import {
  Menu, X, LayoutDashboard, MessageSquare, LayoutGrid, Sparkles,
  Settings, LogOut,
} from 'lucide-react'

interface TopbarProps {
  onMobileMenuToggle: () => void
  mobileDrawerOpen: boolean
  onMobileDrawerClose: () => void
}

function getModuleName(pathname: string): string {
  if (pathname.startsWith('/chat')) return 'Chat'
  if (pathname.startsWith('/studio')) return 'Studio'
  if (pathname.startsWith('/workspace')) return 'Workspace'
  if (pathname === '/settings') return 'Settings'
  if (pathname === '/dashboard') return 'Home'
  return ''
}

export function Topbar({ onMobileMenuToggle, mobileDrawerOpen, onMobileDrawerClose }: TopbarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const moduleName = getModuleName(pathname)

  // Close drawer on navigation
  useEffect(() => {
    onMobileDrawerClose()
  }, [pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  const modules = [
    { label: 'Home', icon: LayoutDashboard, href: '/dashboard', show: true },
    { label: 'Chat', icon: MessageSquare, href: '/chat', show: true },
    { label: 'Workspace', icon: LayoutGrid, href: '/workspace', show: true },
    { label: 'Studio', icon: Sparkles, href: '/studio', show: true },
  ].filter(m => m.show)

  const isActive = (href: string) => {
    if (href === '/chat') return pathname === '/chat' || pathname.startsWith('/chat/')
    return pathname.startsWith(href)
  }

  return (
    <>
      <header className="sticky top-0 z-30 hidden max-lg:flex h-14 items-center gap-3 border-b border-border bg-background/80 px-3 backdrop-blur-xl">
        <button
          onClick={onMobileMenuToggle}
          className="flex items-center justify-center h-10 w-10 rounded-xl text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          aria-label="Open menu"
        >
          {mobileDrawerOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <Link href="/dashboard" className="flex items-center gap-2.5 min-w-0">
          <LogoMark className="h-8 w-8" />
          <span className="font-display text-base font-semibold tracking-tight truncate">
            Social Studio
          </span>
          {moduleName ? (
            <span className="text-muted-foreground text-sm truncate hidden sm:inline">/ {moduleName}</span>
          ) : null}
        </Link>
        <div className="flex-1" />
        <NotificationBell />
        <ThemeToggle />
      </header>

      {/* Mobile drawer overlay */}
      {mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in-0" onClick={onMobileDrawerClose} />
          <aside className="absolute inset-y-0 left-0 w-[86vw] max-w-80 bg-sidebar border-r border-sidebar-border flex flex-col shadow-[0_0_80px_-10px_oklch(0_0_0/0.8)] animate-in slide-in-from-left-4 duration-200">
            <div className="flex items-center h-16 px-4 shrink-0 border-b border-sidebar-border">
              <Logo />
              <div className="flex-1" />
              <button
                onClick={onMobileDrawerClose}
                className="flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
              {modules.map(mod => (
                <Link
                  key={mod.href}
                  href={mod.href}
                  className={cn(
                    'flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition-colors',
                    isActive(mod.href)
                      ? 'bg-primary/15 text-primary font-medium'
                      : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                  )}
                >
                  <mod.icon className="h-5 w-5 shrink-0" />
                  <span>{mod.label}</span>
                </Link>
              ))}

              <Link
                href="/settings"
                className={cn(
                  'flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition-colors',
                  pathname === '/settings'
                    ? 'bg-primary/15 text-primary font-medium'
                    : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                )}
              >
                <Settings className="h-5 w-5 shrink-0" />
                <span>Settings</span>
              </Link>
            </nav>

            {/* User footer */}
            <div className="shrink-0 border-t border-sidebar-border p-3 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-panel-raised text-[11px] font-semibold text-foreground ring-1 ring-border shrink-0">
                {user
                  ? (user.display_name || user.email || '?')
                      .split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase()
                  : '?'}
              </div>
              <span className="flex-1 truncate text-sm text-foreground">
                {user?.display_name || user?.email}
              </span>
              <button
                onClick={() => logout()}
                className="flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </aside>
        </div>
      )}
    </>
  )
}
