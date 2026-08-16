'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@platform/auth-ui'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Building2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TenantData {
  id: string
  name: string
  slug: string
  plan: string
  settings: Record<string, string>
  active: boolean
  created_at: string
  updated_at: string
}

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

export function OrganizationTab() {
  const { getToken } = useAuth()
  const [tenant, setTenant] = useState<TenantData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchTenant() {
      try {
        const token = getToken()
        const res = await fetch('/api/auth/tenants/current', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (res.ok) {
          setTenant(await res.json())
        }
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetchTenant()
  }, [getToken])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (!tenant) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          No organization found.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-amber/10 text-amber">
            <Building2 className="h-4 w-4" />
          </span>
          Organization
        </CardTitle>
        <CardDescription>Details about your workspace.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="space-y-2.5">
          <DetailRow label="Name">{tenant.name}</DetailRow>
          <DetailRow label="Slug" className="font-mono text-xs text-muted-foreground">
            {tenant.slug}
          </DetailRow>
          <DetailRow label="Status">
            <Badge variant={tenant.active ? 'success' : 'muted'}>
              {tenant.active ? 'Active' : 'Inactive'}
            </Badge>
          </DetailRow>
          <DetailRow label="Created">
            {new Date(tenant.created_at).toLocaleDateString()}
          </DetailRow>
          <DetailRow label="Organization ID" className="font-mono text-xs text-muted-foreground">
            {tenant.id}
          </DetailRow>
        </dl>
      </CardContent>
    </Card>
  )
}
