'use client'

import { useAuth, MFASetup } from '@platform/auth-ui'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { ShieldCheck, User } from 'lucide-react'
import { cn } from '@/lib/utils'

function DetailRow({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-panel/40 px-4 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={cn('text-sm font-medium text-foreground text-right truncate', className)}>
        {children}
      </dd>
    </div>
  )
}

export function ProfileTab() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <User className="h-4 w-4" />
            </span>
            Profile
          </CardTitle>
          <CardDescription>Your personal account details.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2.5">
            <DetailRow label="Name">{user?.display_name || '—'}</DetailRow>
            <DetailRow label="Email">{user?.email || '—'}</DetailRow>
            <DetailRow label="Member since">
              {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
            </DetailRow>
            <DetailRow label="User ID" className="font-mono text-xs text-muted-foreground">
              {user?.id || '—'}
            </DetailRow>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-sage/10 text-sage">
              <ShieldCheck className="h-4 w-4" />
            </span>
            Two-Factor Authentication
          </CardTitle>
          <CardDescription>
            Add an extra layer of security to your account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <MFASetup />
        </CardContent>
      </Card>
    </div>
  )
}
