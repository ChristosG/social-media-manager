import type { Metadata, Viewport } from 'next'
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

// Sanctuary type system — editorial serif display + warm humanist body.
// Loaded via next/font (self-hosted at build time → works offline, no runtime CDN).
const fontDisplay = Fraunces({
  subsets: ['latin'],
  variable: '--font-fraunces',
  display: 'swap',
  style: ['normal', 'italic'],
})

const fontSans = Hanken_Grotesk({
  subsets: ['latin'],
  variable: '--font-hanken',
  display: 'swap',
})

const fontMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
})

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
  interactiveWidget: 'resizes-content',
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#060505' },
    { media: '(prefers-color-scheme: light)', color: '#faf6f0' },
  ],
}

const appName = process.env.NEXT_PUBLIC_APP_NAME || 'Social Studio'

// Meta (Facebook) domain verification: rendered server-side into <head> so Meta's
// crawler sees it (a JS-injected tag would fail verification). Optional for Dev-mode
// OAuth; kept here so the domain stays verified if the app ever leaves Dev mode.
const fbDomainVerification =
  process.env.NEXT_PUBLIC_FB_DOMAIN_VERIFICATION || '4lk2hs4222nr931rz6ow5cm56scz3q'

export const metadata: Metadata = {
  title: {
    default: appName,
    template: `%s · ${appName}`,
  },
  description: `${appName} — the social-media studio for nonprofits with a mission.`,
  verification: {
    other: {
      'facebook-domain-verification': fbDomainVerification,
    },
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fontDisplay.variable} ${fontSans.variable} ${fontMono.variable}`}
    >
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
