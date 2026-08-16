import { Check } from 'lucide-react'
import { Logo, LogoMark } from '@/components/brand'

const VALUE_PROPS = [
  'Draft on-brand posts for any platform in seconds',
  'Grounded in your mission, programs, and voice',
  'From first idea to ready-to-publish — in one place',
]

/**
 * Editorial split shell for the auth surfaces.
 *
 * NOTE: the auth-ui package pages (Login/Register/Forgot/Reset) and the
 * onboarding page each render their OWN `min-h-screen` centering wrapper, so the
 * right column intentionally does not add competing height/centering — it just
 * hosts `{children}`, which self-centers within the grid cell. The left panel
 * (lg+) carries the brand/mission; on mobile a compact mark floats above the
 * self-centered card.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* LEFT — brand / mission panel (lg+ only) */}
      <aside className="relative hidden overflow-hidden border-r border-border bg-background lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div className="pointer-events-none absolute inset-0 bg-ambient" />
        <div className="pointer-events-none absolute inset-0 bg-grain" />

        <div className="relative z-10">
          <Logo />
        </div>

        <div className="reveal-stagger relative z-10 max-w-lg">
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-foreground xl:text-[3.25rem]">
            Tell your nonprofit&apos;s{' '}
            <span className="text-gradient-warm">story</span>.
          </h1>

          <p className="mt-5 text-base leading-relaxed text-muted-foreground xl:text-lg">
            Your mission-driven social-media studio — ideas, drafts, and answers
            grounded in the work you do.
          </p>

          <ul className="mt-8 space-y-3.5">
            {VALUE_PROPS.map((prop) => (
              <li key={prop} className="flex items-start gap-3">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                <span className="text-sm leading-relaxed text-muted-foreground">
                  {prop}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 text-xs text-muted-foreground">
          Self-hosted. Your data stays yours.
        </div>
      </aside>

      {/* RIGHT — hosts the self-centering auth/onboarding child */}
      <main className="relative">
        {/* Mobile-only floating brand mark (lg+ uses the left panel instead) */}
        <div className="pointer-events-none absolute inset-x-0 top-8 z-10 flex justify-center lg:hidden">
          <LogoMark className="h-11 w-11" glyphClassName="h-[50%] w-[50%]" />
        </div>

        {children}
      </main>
    </div>
  )
}
