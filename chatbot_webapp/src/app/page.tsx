'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@platform/auth-ui'
import { LogoMark } from '@/components/brand'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading) {
      router.replace(isAuthenticated ? '/chat' : '/login')
    }
  }, [isAuthenticated, isLoading, router])

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 bg-ambient" />
      <LogoMark
        className="relative z-10 h-14 w-14 animate-pulse"
        glyphClassName="h-[50%] w-[50%]"
      />
    </div>
  )
}
