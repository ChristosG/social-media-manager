'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useAuth } from '@platform/auth-ui'
import { icons } from './icons'
import { cn } from '@/lib/utils'

export function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  if (!user) return null

  const initials = (user.display_name || user.email || '?')
    .split(' ')
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90"
        aria-label="User menu"
      >
        {initials}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-lg border bg-card p-1 shadow-lg">
          <div className="px-3 py-2">
            <p className="text-sm font-medium text-card-foreground">{user.display_name}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-border" />
          <Link
            href="/settings"
            onClick={() => setOpen(false)}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm text-card-foreground',
              'hover:bg-accent hover:text-accent-foreground',
            )}
          >
            <icons.settings className="h-4 w-4" />
            Settings
          </Link>
          <button
            onClick={() => {
              setOpen(false)
              logout()
            }}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-card-foreground',
              'hover:bg-accent hover:text-accent-foreground',
            )}
          >
            <icons.logOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
