'use client'

import { useRouter } from 'next/navigation'
import { AuthProvider, ThemeProvider } from '@platform/auth-ui'

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  return (
    <ThemeProvider>
      <AuthProvider
        apiUrl="/api/auth"
        onNavigate={(path) => router.push(path)}
      >
        {children}
      </AuthProvider>
    </ThemeProvider>
  )
}
