'use client'

import { useEffect, useRef } from 'react'
import { RefreshCw, ArrowLeft } from 'lucide-react'
import { LogoMark } from '@/components/brand'

/**
 * Error boundary for the authenticated app. Before this existed, a transient cold-start failure (a
 * just-redeployed backend, a slow RSC fetch right after the auth bootstrap) bubbled to Next.js's bare
 * built-in "This page couldn't load" page — which looked broken and made the user reload by hand.
 *
 * Most of these are transient, so we self-heal ONCE: auto-call reset() shortly after mounting. A successful
 * (app) layout mount clears the guard flag (see (app)/layout.tsx), so a PERSISTENT error doesn't loop — it
 * falls through to this branded panel with manual Reload / Back.
 */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const tried = useRef(false)

  useEffect(() => {
    const KEY = 'ss.err.autoretry'
    let last = 0
    try { last = Number(sessionStorage.getItem(KEY) || 0) } catch { /* ignore */ }
    // Auto-retry at most once per 15s window — enough to ride out a cold backend without a reload loop.
    if (!tried.current && Date.now() - last > 15000) {
      tried.current = true
      try { sessionStorage.setItem(KEY, String(Date.now())) } catch { /* ignore */ }
      const t = setTimeout(() => reset(), 500)
      return () => clearTimeout(t)
    }
  }, [reset])

  return (
    <div className="relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
      <div className="pointer-events-none absolute inset-0 bg-ambient" />
      <LogoMark className="relative z-10 mb-6 h-12 w-12 animate-pulse" glyphClassName="h-[50%] w-[50%]" />
      <h1 className="relative z-10 font-display text-xl font-semibold text-foreground">Reconnecting…</h1>
      <p className="relative z-10 mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        That page didn’t finish loading — usually just the studio waking up. It should retry on its own; if it
        doesn’t, give it a nudge.
      </p>
      <div className="relative z-10 mt-6 flex items-center gap-2">
        <button
          onClick={() => reset()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <RefreshCw className="h-4 w-4" /> Reload
        </button>
        <button
          onClick={() => history.back()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
      </div>
    </div>
  )
}
