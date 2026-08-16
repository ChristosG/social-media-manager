'use client'

import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useNotifications } from '@/hooks/use-notifications'

/**
 * Single global owner of "new notification → toast". MUST be mounted exactly once
 * in the app shell — never inside a component (like NotificationBell) that can mount
 * more than once, or each mount fires its own toast and the user sees duplicates.
 *
 * Renders nothing; it only watches the notifications query (deduped with the bell's
 * own useNotifications via the shared query key) and pops one sonner toast per newly
 * seen unread notification. Seeds the seen-set on first load so we don't replay
 * notifications the user already knew about.
 *
 * Durable, server-recorded events (publish_ok / publish_failed) are owned HERE.
 * Transient/optimistic states that never create a notification row (scheduled,
 * still-publishing, duplicate confirm) stay owned by the action that triggered them.
 */
export function NotificationToaster() {
  const { data } = useNotifications()
  const items = data?.items
  const seenIds = useRef<Set<string>>(new Set())
  const seeded = useRef(false)

  useEffect(() => {
    if (!items) return
    if (!seeded.current) {
      items.forEach((n) => seenIds.current.add(n.id))
      seeded.current = true
      return
    }
    for (const n of items) {
      if (n.read) continue
      if (seenIds.current.has(n.id)) continue
      seenIds.current.add(n.id)
      if (n.type === 'publish_ok') toast.success(n.title)
      else if (n.type === 'publish_failed') toast.error(n.title, { description: n.body || undefined })
      else toast(n.title, { description: n.body || undefined })
    }
  }, [items])

  return null
}
