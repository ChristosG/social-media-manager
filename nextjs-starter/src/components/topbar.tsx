'use client'

import { usePathname } from 'next/navigation'
import { ThemeToggle } from '@platform/auth-ui'
import { UserMenu } from './user-menu'
import { icons } from './icons'
import { navigation } from '@/config/navigation'

interface TopbarProps {
  onMenuClick: () => void
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const pathname = usePathname()

  const currentNav = navigation.find((item) => pathname.startsWith(item.href))
  const title = currentNav?.label || 'Page'

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-4 border-b bg-background/80 px-4 backdrop-blur-sm lg:px-6">
      <button
        onClick={onMenuClick}
        className="rounded-md p-2 text-foreground hover:bg-accent lg:hidden"
        aria-label="Open menu"
      >
        <icons.menu className="h-5 w-5" />
      </button>

      <h1 className="text-lg font-semibold text-foreground">{title}</h1>

      <div className="ml-auto flex items-center gap-3">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  )
}
