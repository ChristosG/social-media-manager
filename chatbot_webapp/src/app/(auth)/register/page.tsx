'use client'

import { useRouter } from 'next/navigation'
import { RegisterPage } from '@platform/auth-ui'

export default function Register() {
  const router = useRouter()

  return (
    <RegisterPage
      onNavigate={(path) => router.push(path)}
      onSuccess={() => router.push('/onboarding')}
      showOAuth
    />
  )
}
