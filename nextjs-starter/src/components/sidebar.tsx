'use client'

import { usePathname } from 'next/navigation'
import { navigation } from '@/config/navigation'
import { NavItem } from './nav-item'
import { icons } from './icons'
import { cn } from '@/lib/utils'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside
      className={cn(
        'hidden lg:flex flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200',
        collapsed ? 'w-[var(--pau-sidebar-collapsed-width)]' : 'w-[var(--pau-sidebar-width)]',
      )}
    >
      <div className={cn(
        'flex h-16 items-center border-b border-sidebar-border px-4',
        collapsed ? 'justify-center' : 'justify-between',
      )}>
        {!collapsed && (
          <span className="text-lg font-bold text-sidebar-foreground">Platform</span>
        )}
        <button
          onClick={onToggle}
          className="rounded-md p-1.5 text-sidebar-foreground hover:bg-accent"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <icons.chevronRight className="h-4 w-4" /> : <icons.chevronLeft className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 p-2">
        {navigation.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            isActive={pathname.startsWith(item.href)}
            collapsed={collapsed}
          />
        ))}
      </nav>
    </aside>
  )
}
