'use client'

import { useRouter } from 'next/navigation'
import { ForgotPasswordPage } from '@platform/auth-ui'

export default function ForgotPassword() {
  const router = useRouter()

  return (
    <ForgotPasswordPage
      onNavigate={(path) => router.push(path)}
    />
  )
}
