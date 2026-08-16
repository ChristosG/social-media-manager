import type { Metadata } from 'next'
import '@platform/auth-ui/styles.css'
import { Providers } from './providers'

export const metadata: Metadata = {
  title: 'Auth Demo',
  description: 'Demo app for @platform/auth-ui',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
