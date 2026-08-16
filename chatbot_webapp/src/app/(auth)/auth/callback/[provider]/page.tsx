'use client'

import { useParams } from 'next/navigation'
import { OAuthCallbackHandler } from '@platform/auth-ui'

export default function OAuthCallback() {
  const params = useParams()
  const provider = params.provider as string

  // Full-page navigation (not router.push) so the app re-initializes the session from the freshly-set
  // refresh cookie — a client-side push races the auth state and bounces to /login (needing a reload).
  return (
    <OAuthCallbackHandler
      provider={provider}
      onSuccess={() => { window.location.href = '/dashboard' }}
      onError={() => { window.location.href = '/login' }}
    />
  )
}
