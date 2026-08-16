'use client'

import { useRouter, useParams } from 'next/navigation'
import { OAuthCallbackHandler } from '@platform/auth-ui'

export default function OAuthCallback() {
  const router = useRouter()
  const params = useParams()
  const provider = params.provider as string

  return (
    <OAuthCallbackHandler
      provider={provider}
      onSuccess={() => router.push('/dashboard')}
      onError={() => router.push('/login')}
    />
  )
}
