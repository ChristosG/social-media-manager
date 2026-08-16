'use client'

import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { UserPlus, Users } from 'lucide-react'

export function TeamTab() {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <Users className="h-4 w-4" />
            </span>
            Team
          </CardTitle>
          <CardDescription>Manage your organization members and roles.</CardDescription>
        </div>
        <Button disabled className="gap-2 shrink-0">
          <UserPlus className="h-4 w-4" />
          Invite member
        </Button>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-panel/30 px-6 py-12 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary mb-4">
            <Users className="h-6 w-6" />
          </span>
          <p className="font-display text-base font-semibold tracking-tight text-foreground">
            Team management coming soon
          </p>
          <p className="mt-1.5 max-w-sm text-sm text-muted-foreground leading-relaxed">
            Invite teammates, assign roles, and manage permissions — all from here.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <Badge variant="outline">Owner</Badge>
            <Badge variant="muted">Admin</Badge>
            <Badge variant="muted">Member</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
