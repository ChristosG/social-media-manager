'use client'

import Link from 'next/link'
import { icons, type IconName } from './icons'
import { cn } from '@/lib/utils'

interface NavItemProps {
  href: string
  label: string
  icon: IconName
  isActive: boolean
  collapsed: boolean
  onClick?: () => void
}

export function NavItem({ href, label, icon, isActive, collapsed, onClick }: NavItemProps) {
  const Icon = icons[icon]

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        isActive
          ? 'bg-sidebar-active text-sidebar-active-foreground'
          : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground',
        collapsed && 'justify-center px-2',
      )}
      title={collapsed ? label : undefined}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!collapsed && <span>{label}</span>}
    </Link>
  )
}
