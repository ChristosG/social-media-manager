'use client'

import { useRouter } from 'next/navigation'
import {
  Bell, CheckCircle2, AlertTriangle, Link2, Clock, MessageCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Popover, PopoverTrigger, PopoverContent,
} from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import {
  useNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '@/hooks/use-notifications'
import type { AppNotification } from '@/lib/studio-api'

// ─── helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function NotifTypeIcon({ type }: { type: string }) {
  const cls = 'h-4 w-4 shrink-0'
  switch (type) {
    case 'publish_ok':
      return <CheckCircle2 className={cn(cls, 'text-emerald-500')} />
    case 'publish_failed':
      return <AlertTriangle className={cn(cls, 'text-amber-500')} />
    case 'connected':
      return <Link2 className={cn(cls, 'text-primary')} />
    case 'scheduled':
      return <Clock className={cn(cls, 'text-muted-foreground')} />
    case 'comment':
      return <MessageCircle className={cn(cls, 'text-primary')} />
    default:
      return <Bell className={cn(cls, 'text-muted-foreground')} />
  }
}

// ─── Item row ────────────────────────────────────────────────────────────────

function NotifItem({
  item,
  onRead,
}: {
  item: AppNotification
  onRead: (id: string) => void
}) {
  const router = useRouter()

  function handleClick() {
    onRead(item.id)
    if (!item.link) return
    // Validate the scheme before navigating — never pass an unvalidated string to router.push/window.open
    // (guards against javascript: / data: / protocol-relative //evil.com open-redirect & XSS vectors).
    const link = item.link
    if (link.startsWith('/') && !link.startsWith('//')) {
      router.push(link)                       // safe in-app relative path
    } else {
      try {
        const u = new URL(link)
        if (u.protocol === 'https:' || u.protocol === 'http:') {
          window.open(u.toString(), '_blank', 'noopener,noreferrer')
        }
      } catch {
        /* malformed / unsafe link — ignore */
      }
    }
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        'w-full text-left px-3 py-2.5 flex gap-3 items-start transition-colors',
        'hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
        !item.read && 'bg-primary/5',
      )}
    >
      {/* Unread accent dot */}
      <span
        className={cn(
          'mt-1 h-1.5 w-1.5 shrink-0 rounded-full',
          !item.read ? 'bg-primary' : 'bg-transparent',
        )}
        aria-hidden
      />

      <NotifTypeIcon type={item.type} />

      <div className="min-w-0 flex-1">
        <p
          className={cn(
            'text-sm leading-snug',
            item.read ? 'text-muted-foreground font-normal' : 'text-foreground font-medium',
          )}
        >
          {item.title}
        </p>
        {item.body ? (
          <p className="mt-0.5 text-xs text-muted-foreground break-words whitespace-pre-line line-clamp-6">{item.body}</p>
        ) : null}
        <p className="mt-1 text-[11px] text-muted-foreground/60">{relativeTime(item.created_at)}</p>
      </div>
    </button>
  )
}

// ─── Bell + Popover ───────────────────────────────────────────────────────────

export function NotificationBell() {
  const { data } = useNotifications()
  const { mutate: markRead } = useMarkNotificationRead()
  const { mutate: markAll, isPending: markingAll } = useMarkAllNotificationsRead()

  const items = data?.items ?? []
  const unreadCount = data?.unread_count ?? 0

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="relative flex items-center justify-center h-9 w-9 rounded-xl text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        >
          <Bell className="h-4.5 w-4.5 h-[1.125rem] w-[1.125rem]" />
          {unreadCount > 0 && (
            <span
              className={cn(
                'absolute top-1 right-1 flex items-center justify-center rounded-full',
                'bg-primary text-[10px] font-semibold text-primary-foreground leading-none',
                unreadCount < 10 ? 'h-4 w-4' : 'h-4 min-w-4 px-0.5',
              )}
              aria-hidden
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={8}
        className="w-[min(20rem,calc(100vw-1.5rem))] p-0 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-border">
          <span className="text-sm font-semibold text-foreground">Notifications</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
            disabled={unreadCount === 0 || markingAll}
            onClick={() => markAll()}
          >
            Mark all read
          </Button>
        </div>

        {/* List */}
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-10 px-4 text-center">
            <Bell className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>
          </div>
        ) : (
          <div className="max-h-[min(360px,60vh)] overflow-y-auto overscroll-contain">
            <div className="divide-y divide-border/60">
              {items.map(item => (
                <NotifItem
                  key={item.id}
                  item={item}
                  onRead={id => markRead(id)}
                />
              ))}
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
