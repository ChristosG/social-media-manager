'use client'

import { usePathname } from 'next/navigation'

export function ContextualSidebar() {
  const pathname = usePathname()

  // Chat manages its own sidebar inside ChatShell
  // Settings and dashboard have no sidebar
  if (
    pathname.startsWith('/chat') ||
    pathname === '/settings' ||
    pathname === '/dashboard' ||
    pathname.startsWith('/studio')
  ) {
    return null
  }

  return null
}
