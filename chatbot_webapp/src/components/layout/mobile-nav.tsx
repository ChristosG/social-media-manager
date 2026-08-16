'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { LayoutDashboard, MessageSquare, LayoutGrid, Sparkles, Settings } from 'lucide-react'

export function MobileNav() {
  const pathname = usePathname()

  // Hide bottom nav on chat pages — chat has its own full-height input
  if (pathname === '/chat' || pathname.startsWith('/chat/')) {
    return null
  }

  const items = [
    { label: 'Home', icon: LayoutDashboard, href: '/dashboard', show: true },
    { label: 'Workspace', icon: LayoutGrid, href: '/workspace', show: true },
    { label: 'Chat', icon: MessageSquare, href: '/chat', show: true },
    { label: 'Studio', icon: Sparkles, href: '/studio', show: true },
    { label: 'Settings', icon: Settings, href: '/settings', show: true },
  ].filter(i => i.show)

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard'
    if (href === '/chat') return pathname === '/chat' || pathname.startsWith('/chat/')
    return pathname.startsWith(href)
  }

  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 hidden max-lg:flex items-stretch justify-around border-t border-border bg-background/90 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]">
      {items.map(item => {
        const active = isActive(item.href)
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'group relative flex flex-1 flex-col items-center gap-1 px-1 pt-2.5 pb-2 text-[10px] font-medium transition-colors',
              active ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            <span
              className={cn(
                'flex items-center justify-center h-8 w-12 rounded-full transition-colors',
                active ? 'bg-primary/15' : 'group-hover:bg-accent/60',
              )}
            >
              <item.icon className="h-5 w-5" />
            </span>
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
