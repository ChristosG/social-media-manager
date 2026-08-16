'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { navigation } from '@/config/navigation'
import { NavItem } from './nav-item'
import { icons } from './icons'

interface MobileSidebarProps {
  open: boolean
  onClose: () => void
}

export function MobileSidebar({ open, onClose }: MobileSidebarProps) {
  const pathname = usePathname()

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = ''
      }
    }
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="fixed inset-y-0 left-0 w-[var(--pau-sidebar-width)] bg-sidebar shadow-xl">
        <div className="flex h-16 items-center justify-between border-b border-sidebar-border px-4">
          <span className="text-lg font-bold text-sidebar-foreground">Platform</span>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-sidebar-foreground hover:bg-accent"
            aria-label="Close sidebar"
          >
            <icons.x className="h-5 w-5" />
          </button>
        </div>

        <nav className="space-y-1 p-2">
          {navigation.map((item) => (
            <NavItem
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              isActive={pathname.startsWith(item.href)}
              collapsed={false}
              onClick={onClose}
            />
          ))}
        </nav>
      </div>
    </div>
  )
}
