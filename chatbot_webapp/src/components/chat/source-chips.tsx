'use client'

import Link from 'next/link'
import { Globe, Instagram, Facebook, BookMarked, Megaphone } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isSafeHref } from '@/lib/image-url'
import type { SourceCitation } from '@/lib/chat-api'

/** The org's OWN socials are framed as voice/style reference; everything else is external grounding. */
function isOwnPost(kind: string) {
  return kind === 'facebook' || kind === 'instagram'
}

function hostOf(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

function chipIcon(kind: string) {
  if (kind === 'instagram') return Instagram
  if (kind === 'facebook') return Facebook
  return Globe
}

/**
 * Click-through provenance for a grounded answer or a set of suggestions. The org's own past posts
 * (the assistant's voice reference) are visually distinct from external web/news sources it cited.
 */
export function SourceChips({ sources }: { sources?: SourceCitation[] }) {
  if (!sources?.length) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/70">
        <BookMarked className="h-3 w-3" /> Sources
      </span>
      {sources.map((s, i) => {
        // A prior CAMPAIGN the planner drew on — an INTERNAL deep-link (not an external site), so it routes
        // in-app to that campaign rather than opening a new tab. The url is built by us (/workspace?…&c=<id>).
        if (s.kind === 'campaign') {
          return (
            <Link
              key={`camp-${s.url}-${i}`}
              href={s.url}
              title={s.snippet ? `${s.title} — ${s.snippet}` : s.title}
              className="inline-flex max-w-[14rem] items-center gap-1 truncate rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] text-primary transition-colors hover:bg-primary/20"
            >
              <Megaphone className="h-3 w-3 shrink-0" />
              <span className="truncate">{s.title || 'past campaign'}</span>
            </Link>
          )
        }
        const own = isOwnPost(s.kind)
        const Icon = chipIcon(s.kind)
        const label = own ? 'your post' : hostOf(s.url)
        // Only navigate to http(s)/mailto URLs — a citation can come from external grounding, so a
        // javascript:/data: href must not become a clickable XSS sink. Unsafe → render a dead chip.
        const href = isSafeHref(s.url) ? s.url : undefined
        return (
          <a
            key={`${s.url}-${i}`}
            href={href}
            target="_blank"
            rel="noreferrer"
            title={s.title || s.snippet || s.url}
            className={cn(
              'inline-flex max-w-[14rem] items-center gap-1 truncate rounded-full border px-2 py-0.5 text-[11px] transition-colors',
              own
                ? 'border-amber/30 bg-amber/10 text-amber hover:bg-amber/20'
                : 'border-border bg-panel/40 text-muted-foreground hover:bg-panel/70 hover:text-foreground',
            )}
          >
            <Icon className="h-3 w-3 shrink-0" />
            <span className="truncate">{label}</span>
          </a>
        )
      })}
    </div>
  )
}
