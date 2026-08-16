'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import { ResetPasswordPage } from '@platform/auth-ui'

function ResetPasswordInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''

  if (!token) {
    return (
      <div className="rounded-lg bg-destructive/10 p-6 text-center">
        <p className="text-sm font-medium text-destructive">
          Missing reset token. Please use the link from your email.
        </p>
      </div>
    )
  }

  return (
    <ResetPasswordPage
      token={token}
      onNavigate={(path) => router.push(path)}
    />
  )
}

export default function ResetPassword() {
  return (
    <Suspense>
      <ResetPasswordInner />
    </Suspense>
  )
}
