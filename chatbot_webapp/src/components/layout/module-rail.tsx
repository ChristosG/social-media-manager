'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@platform/auth-ui'
import { ThemeToggle } from '@platform/auth-ui'
import { cn } from '@/lib/utils'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { LogoMark } from '@/components/brand'
import { NotificationBell } from '@/components/layout/notification-bell'
import {
  LayoutDashboard, MessageSquare, LayoutGrid, Settings, LogOut, Sparkles,
} from 'lucide-react'

interface ModuleItem {
  key: string
  label: string
  icon: React.ElementType
  href: string
  show: boolean
}

export function ModuleRail() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  const modules: ModuleItem[] = [
    { key: 'dashboard', label: 'Home', icon: LayoutDashboard, href: '/dashboard', show: true },
    { key: 'chat', label: 'Chat', icon: MessageSquare, href: '/chat', show: true },
    { key: 'workspace', label: 'Workspace', icon: LayoutGrid, href: '/workspace', show: true },
    { key: 'studio', label: 'Studio', icon: Sparkles, href: '/studio', show: true },
  ].filter(m => m.show)

  const isActive = (href: string) => {
    if (href === '/chat') return pathname === '/chat' || pathname.startsWith('/chat/')
    return pathname.startsWith(href)
  }

  const initials = user
    ? (user.display_name || user.email || '?')
        .split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase()
    : '?'

  return (
    <aside className="hidden lg:flex flex-col items-center w-16 bg-sidebar border-r border-sidebar-border shrink-0 py-3">
      {/* Brand mark — links home */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Link href="/dashboard" className="mb-4 transition-transform hover:scale-105 active:scale-95">
            <LogoMark className="h-10 w-10" />
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">Social Studio</TooltipContent>
      </Tooltip>

      {/* Module icons */}
      <nav className="flex flex-col items-center gap-1.5 flex-1">
        {modules.map(mod => {
          const active = isActive(mod.href)
          return (
            <Tooltip key={mod.key}>
              <TooltipTrigger asChild>
                <Link
                  href={mod.href}
                  className={cn(
                    'relative flex items-center justify-center h-11 w-11 rounded-xl transition-all duration-200',
                    active
                      ? 'bg-primary/15 text-primary'
                      : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                  )}
                >
                  {active && (
                    <span className="absolute -left-1.5 top-2.5 bottom-2.5 w-[3px] rounded-full bg-primary shadow-[0_0_10px_0_var(--pau-glow-primary)]" />
                  )}
                  <mod.icon className="h-[1.15rem] w-[1.15rem]" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">{mod.label}</TooltipContent>
            </Tooltip>
          )
        })}
      </nav>

      {/* Bottom: notifications, theme toggle, settings, sign out, avatar */}
      <div className="flex flex-col items-center gap-1.5">
        <NotificationBell />
        <ThemeToggle />

        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href="/settings"
              className={cn(
                'flex items-center justify-center h-11 w-11 rounded-xl transition-all duration-200',
                pathname === '/settings'
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
              )}
            >
              <Settings className="h-[1.15rem] w-[1.15rem]" />
            </Link>
          </TooltipTrigger>
          <TooltipContent side="right">Settings</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => logout()}
              className="flex items-center justify-center h-11 w-11 rounded-xl text-muted-foreground hover:bg-accent/70 hover:text-foreground transition-all duration-200"
              aria-label="Sign out"
            >
              <LogOut className="h-[1.15rem] w-[1.15rem]" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Sign out</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="mt-1 flex items-center justify-center h-9 w-9 rounded-full bg-panel-raised text-[11px] font-semibold text-foreground ring-1 ring-border cursor-default">
              {initials}
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">{user?.display_name || user?.email}</TooltipContent>
        </Tooltip>
      </div>
    </aside>
  )
}
