'use client'

import { useRouter } from 'next/navigation'
import { LoginPage } from '@platform/auth-ui'

export default function Login() {
  const router = useRouter()

  return (
    <LoginPage
      onNavigate={(path) => router.push(path)}
      onSuccess={() => router.push('/onboarding')}
      showOAuth
    />
  )
}
