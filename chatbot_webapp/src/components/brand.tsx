import type { SVGProps } from 'react'
import { cn } from '@/lib/utils'

/**
 * Broadcast glyph — a nonprofit amplifying its voice. Reads as "signal / reach",
 * the heart of a social-media studio. Drawn in currentColor so it inherits the
 * tile's foreground.
 */
export function BroadcastGlyph({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      <path d="M4 11a9 9 0 0 1 9 9" />
      <path d="M4 4a16 16 0 0 1 16 16" />
      <circle cx="5" cy="19" r="1.7" fill="currentColor" stroke="none" />
    </svg>
  )
}

/**
 * The Social Studio mark — the phoenix brand glyph on its coral field, clipped to
 * a squircle tile with the warm ring + glow. Size via className (e.g. `h-9 w-9`).
 * The artwork ships its own coral background, so it stays on-brand across themes.
 * `glyphClassName` is accepted for call-site compatibility (it tunes the artwork).
 */
export function LogoMark({
  className,
  glyphClassName,
}: {
  className?: string
  glyphClassName?: string
}) {
  return (
    <span
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-[30%]',
        'shadow-[0_6px_22px_-8px_var(--pau-glow-primary)] ring-1 ring-inset ring-white/15',
        className,
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- tiny static brand asset, no layout shift */}
      <img
        src="/brand-mark.png"
        alt="Social Studio"
        className={cn('h-full w-full object-cover', glyphClassName)}
        draggable={false}
      />
    </span>
  )
}

/**
 * "Social Studio" wordmark in the Fraunces display serif. `Studio` carries the
 * warm gradient for an editorial accent.
 */
export function Wordmark({
  className,
  appName = 'Social Studio',
}: {
  className?: string
  appName?: string
}) {
  const [first, ...rest] = appName.split(' ')
  const second = rest.join(' ')
  return (
    <span className={cn('font-display text-lg font-semibold tracking-tight leading-none', className)}>
      {first}
      {second ? <span className="text-gradient-warm">{' '}{second}</span> : null}
    </span>
  )
}

/** Mark + wordmark lockup. */
export function Logo({
  className,
  markClassName,
  wordmarkClassName,
  appName,
}: {
  className?: string
  markClassName?: string
  wordmarkClassName?: string
  appName?: string
}) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark className={cn('h-8 w-8', markClassName)} />
      <Wordmark appName={appName} className={wordmarkClassName} />
    </span>
  )
}
