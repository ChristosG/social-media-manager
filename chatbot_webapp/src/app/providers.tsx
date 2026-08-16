'use client'

import { useRouter } from 'next/navigation'
import { AuthProvider, ThemeProvider } from '@platform/auth-ui'
import { QueryClientProvider } from '@tanstack/react-query'
import { getQueryClient } from '@/lib/query-client'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { SocialResultToast } from '@/components/social-result-toast'

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const queryClient = getQueryClient()

  return (
    <ThemeProvider defaultTheme="dark">
      <AuthProvider
        apiUrl="/api/auth"
        onNavigate={(path) => router.push(path)}
      >
        <QueryClientProvider client={queryClient}>
          <TooltipProvider>
            {children}
            <SocialResultToast />
            <Toaster />
          </TooltipProvider>
        </QueryClientProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
