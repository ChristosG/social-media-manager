'use client'

import { useState } from 'react'
import { useAuth } from '@platform/auth-ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ProfileTab } from '@/components/settings/profile-tab'
import { OrganizationTab } from '@/components/settings/organization-tab'
import { TeamTab } from '@/components/settings/team-tab'
import { ObservabilityTab } from '@/components/settings/observability-tab'

export default function Settings() {
  const { user } = useAuth()
  const canManageTenant = user?.permissions?.includes('tenant:manage') ?? false

  // URL-driven tab so other pages can deep-link (e.g. Studio → "Full traces" → /settings?tab=observability).
  const [tab, setTab] = useState(
    () => (typeof window === 'undefined' ? 'profile'
      : new URLSearchParams(window.location.search).get('tab') || 'profile'),
  )
  const onTab = (v: string) => {
    setTab(v)
    if (typeof window !== 'undefined') window.history.replaceState({}, '', `/settings?tab=${v}`)
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-6 sm:py-10 reveal-stagger">
      <header className="mb-6 sm:mb-8">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">
          Settings
        </h1>
        <p className="mt-1.5 text-sm sm:text-base text-muted-foreground leading-relaxed">
          Manage your account, organization, and team.
        </p>
      </header>

      <Tabs value={tab} onValueChange={onTab}>
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          {canManageTenant && (
            <>
              <TabsTrigger value="organization">Organization</TabsTrigger>
              <TabsTrigger value="team">Team</TabsTrigger>
              <TabsTrigger value="observability">Observability</TabsTrigger>
            </>
          )}
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>

        {canManageTenant && (
          <>
            <TabsContent value="organization">
              <OrganizationTab />
            </TabsContent>
            <TabsContent value="team">
              <TeamTab />
            </TabsContent>
            <TabsContent value="observability">
              <ObservabilityTab />
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  )
}
