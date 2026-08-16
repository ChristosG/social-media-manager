'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight, Download, DownloadCloud } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isSafeImageUrl, toDownloadUrl, triggerDownload } from '@/lib/image-url'

/**
 * Swipeable carousel for generated image variations. Fed by the agent's ```ss-gallery``` block.
 * URLs are allowlisted (no javascript:/data:text). Downloads serve the original PNG (max quality).
 * Overlay controls use black/white — they sit on arbitrary images, not theme surfaces.
 */
export function ImageCarousel({ urls }: { urls: string[] }) {
  const safe = urls.filter(isSafeImageUrl)
  const [i, setI] = useState(0)
  if (!safe.length) return null
  const n = safe.length

  if (n === 1) {
    return (
      <span className="group relative my-3 block w-full max-w-md">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={safe[0]} alt="Generated image" loading="lazy" className="w-full rounded-xl border border-border" />
        <a
          href={toDownloadUrl(safe[0])}
          download="image.png"
          className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full bg-black/60 text-white opacity-0 backdrop-blur-sm transition hover:bg-black/80 group-hover:opacity-100"
          aria-label="Download image"
        >
          <Download className="h-4 w-4" />
        </a>
      </span>
    )
  }

  const go = (d: number) => setI((p) => (p + d + n) % n)
  const downloadAll = () => safe.forEach((u, idx) => setTimeout(() => triggerDownload(u, `variation-${idx + 1}.png`), idx * 400))

  return (
    <div className="my-3 w-full max-w-md">
      <div className="relative overflow-hidden rounded-xl border border-border bg-card">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={safe[i]} alt={`Variation ${i + 1} of ${n}`} loading="lazy" className="block aspect-square w-full object-cover" />

        <div className="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
          {i + 1} / {n}
        </div>

        <a
          href={toDownloadUrl(safe[i])}
          download={`variation-${i + 1}.png`}
          className="absolute left-2 top-2 grid h-7 w-7 place-items-center rounded-full bg-black/60 text-white backdrop-blur-sm transition hover:bg-black/80"
          aria-label="Download this variation"
        >
          <Download className="h-3.5 w-3.5" />
        </a>

        <button
          type="button" onClick={() => go(-1)} aria-label="Previous variation"
          className="absolute left-2 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-black/55 text-white backdrop-blur-sm transition hover:bg-primary hover:text-primary-foreground"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          type="button" onClick={() => go(1)} aria-label="Next variation"
          className="absolute right-2 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-black/55 text-white backdrop-blur-sm transition hover:bg-primary hover:text-primary-foreground"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {safe.map((_, idx) => (
            <button
              key={idx} type="button" onClick={() => setI(idx)} aria-label={`Go to variation ${idx + 1}`}
              className={cn('h-1.5 rounded-full transition-all', idx === i ? 'w-5 bg-primary' : 'w-1.5 bg-muted-foreground/40 hover:bg-muted-foreground')}
            />
          ))}
        </div>
        <button
          type="button" onClick={downloadAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
        >
          <DownloadCloud className="h-3.5 w-3.5" />
          Download all
        </button>
      </div>
    </div>
  )
}
