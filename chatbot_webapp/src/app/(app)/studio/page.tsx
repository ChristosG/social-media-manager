'use client'
import { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BookOpen, Globe, ScrollText, Wrench, Brain, SlidersHorizontal } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { VoiceCard } from '@/components/studio/voice-card'
import { TagListCard } from '@/components/studio/tag-list-card'
import { CapabilitiesTab } from '@/components/studio/capabilities-tab'
import { ResearchCard } from '@/components/studio/research-card'
import { ProfileCard } from '@/components/studio/profile-card'
import { ProgramsCard } from '@/components/studio/programs-card'
import { LedgerTab } from '@/components/studio/ledger-tab'
import { SourcesTab } from '@/components/studio/sources-tab'
import { KnowledgeTab } from '@/components/studio/knowledge-tab'
import { PromptsTab } from '@/components/settings/prompts-tab'
import {
  useMemory, useCreateMemory, useUpdateMemory, useDeleteMemory,
} from '@/hooks/use-studio'
import type { MemoryEntry } from '@/lib/studio-api'

export default function StudioPage() {
  const memory = useMemory()
  const createMem = useCreateMemory(); const updateMem = useUpdateMemory(); const deleteMem = useDeleteMemory()
  const qc = useQueryClient()
  const [tab, setTab] = useState('memory')

  // The Meta OAuth callback redirects here with ?social=... — drop the user straight on the Sources tab.
  // The success/fail toast is fired by <SocialResultToast> (cookie-driven, survives re-login). We just
  // switch the tab and scrub the query so a refresh won't re-trigger.
  useEffect(() => {
    const social = new URLSearchParams(window.location.search).get('social')
    if (!social) return
    setTab('sources')
    // Returning from a connect/reconnect: the connection list AND the auto-created/removed sources
    // changed server-side — refresh both so the Sources panel reflects it without a manual reload.
    qc.invalidateQueries({ queryKey: ['studio', 'connections'] })
    qc.invalidateQueries({ queryKey: ['studio', 'sources'] })
    window.history.replaceState({}, '', '/studio')
  }, [qc])

  const entries = memory.data?.entries ?? []
  const voice = entries.find((e) => e.kind === 'brand_voice')
  const banned = entries.filter((e) => e.kind === 'banned_topic')
  const pillars = entries.filter((e) => e.kind === 'content_pillar')
  const label = (e: MemoryEntry) => String(e.value.topic ?? e.value.name ?? e.value.descriptor ?? e.key ?? '')

  const saveVoice = async (descriptor: string) => {
    try {
      if (voice) await updateMem.mutateAsync({ id: voice.id, value: { descriptor } })
      else await createMem.mutateAsync({ kind: 'brand_voice', value: { descriptor } })
      toast.success('Brand voice saved')
    } catch { toast.error('Save failed') }
  }
  const addKind = (kind: string, field: string) => async (v: string) => {
    try { await createMem.mutateAsync({ kind, value: { [field]: v } }); toast.success('Added') }
    catch { toast.error('Add failed') }
  }
  const remove = async (id: string) => {
    try { await deleteMem.mutateAsync(id); toast.success('Removed') } catch { toast.error('Remove failed') }
  }

  return (
    <div className="relative">
      {/* Ambient warm wash anchoring the editorial header */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-ambient" />

      <div className="relative mx-auto max-w-4xl px-4 sm:px-6 py-6 sm:py-10 space-y-8">
        <header>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">Studio</h1>
          <p className="mt-2 max-w-2xl text-sm sm:text-base text-muted-foreground leading-relaxed">
            Teach the assistant about your organization — its mission, voice, and what it can do.
            Every edit shapes the next message.
          </p>
        </header>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="w-full justify-start sm:w-auto">
            <TabsTrigger value="memory"><BookOpen /> Memory</TabsTrigger>
            <TabsTrigger value="knowledge"><Brain /> Knowledge</TabsTrigger>
            <TabsTrigger value="ledger"><ScrollText /> Post Ledger</TabsTrigger>
            <TabsTrigger value="capabilities"><Wrench /> Capabilities</TabsTrigger>
            <TabsTrigger value="sources"><Globe /> Sources</TabsTrigger>
            <TabsTrigger value="prompts"><SlidersHorizontal /> Prompts</TabsTrigger>
          </TabsList>

          <TabsContent value="memory" className="space-y-4 reveal-stagger">
            <ResearchCard />
            <ProfileCard />
            <ProgramsCard />
            <VoiceCard title="Brand voice" description="How the assistant should sound."
              value={String(voice?.value.descriptor ?? '')} onSave={saveVoice} saving={createMem.isPending || updateMem.isPending} />
            <TagListCard title="Banned topics" description="The assistant will never mention these."
              items={banned.map((e) => ({ id: e.id, label: label(e) }))}
              onAdd={addKind('banned_topic', 'topic')} onRemove={remove} />
            <TagListCard title="Content pillars" description="Recurring themes to draw from."
              items={pillars.map((e) => ({ id: e.id, label: label(e) }))}
              onAdd={addKind('content_pillar', 'name')} onRemove={remove} />
          </TabsContent>

          <TabsContent value="knowledge">
            <KnowledgeTab />
          </TabsContent>

          <TabsContent value="ledger">
            <LedgerTab />
          </TabsContent>

          <TabsContent value="capabilities">
            <CapabilitiesTab />
          </TabsContent>

          <TabsContent value="sources">
            <SourcesTab />
          </TabsContent>

          <TabsContent value="prompts">
            <PromptsTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
