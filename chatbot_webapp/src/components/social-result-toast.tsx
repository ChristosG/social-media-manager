'use client'
import { useEffect, useRef } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuth } from '@platform/auth-ui'
import { toast } from 'sonner'

/**
 * Surfaces the outcome of the Meta (Facebook/Instagram) OAuth connect flow.
 *
 * The callback can't talk to the SPA directly (it's a full-page browser redirect from Meta), so it drops
 * a short-lived `social_result` cookie. We read it here — mounted above the router, so it fires wherever
 * the user lands, including after a forced re-login (access tokens are in-memory; a full reload without
 * "Remember me" logs the browser out and the query string is lost, but the cookie survives).
 *
 * Fires once, clears the cookie, and routes to Studio→Sources so the freshly linked accounts are in view.
 */
export function SocialResultToast() {
  const { user } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const fired = useRef(false)

  useEffect(() => {
    if (!user || fired.current) return
    const m = document.cookie.match(/(?:^|;\s*)social_result=([^;]+)/)
    if (!m) return
    fired.current = true
    document.cookie = 'social_result=; Max-Age=0; path=/' // consume once

    const [status, detail] = decodeURIComponent(m[1]).split(':')
    if (status === 'connected') {
      const n = Number(detail || 0)
      if (n > 0) toast.success(`Connected ✓ — linked ${n} account${n === 1 ? '' : 's'}`)
      else toast.warning('Connected, but no Pages were found. Make sure your Instagram is Business/Creator and linked to a Facebook Page you admin.')
    } else {
      toast.error(
        detail === 'denied' ? 'Connection cancelled — you can try again anytime.'
        : detail === 'meta' ? "Couldn't reach Meta. Please try connecting again."
        : detail === 'invalid' ? 'Connection link expired or invalid — please start again from Sources.'
        : 'Connection failed — please try again.',
      )
    }

    // Bring them to the Sources tab if they aren't already on Studio (the page reads ?social= to switch tab).
    if (pathname !== '/studio') {
      const q = status === 'connected'
        ? `social=connected&linked=${detail || 0}`
        : `social=error&reason=${detail}`
      router.push(`/studio?${q}`)
    }
  }, [user, pathname, router])

  return null
}
