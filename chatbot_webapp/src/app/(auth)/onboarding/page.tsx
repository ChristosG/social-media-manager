'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth, useApiClient } from '@platform/auth-ui'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { LogoMark } from '@/components/brand'
import { ResearchCard } from '@/components/studio/research-card'
import { studioApi, type ResearchResult } from '@/lib/studio-api'
import {
  Instagram, Facebook, Linkedin, Twitter, Music2,
  ArrowRight, ArrowLeft, Check, Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

const STEPS = ['Organization', 'Research', 'Voice & platform']

const PLATFORMS = [
  { key: 'instagram', label: 'Instagram', Icon: Instagram },
  { key: 'facebook', label: 'Facebook', Icon: Facebook },
  { key: 'linkedin', label: 'LinkedIn', Icon: Linkedin },
  { key: 'twitter', label: 'X', Icon: Twitter },
  { key: 'tiktok', label: 'TikTok', Icon: Music2 },
]

function toSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
}

export default function OnboardingPage() {
  const router = useRouter()
  const { user, isLoading, updateSession, getToken } = useAuth()
  const api = useApiClient()

  const [step, setStep] = useState(0)
  const [orgName, setOrgName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [creating, setCreating] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [error, setError] = useState('')

  // Enrichment captured in steps 1-2 (all optional / skippable; also editable later in Studio).
  const [research, setResearch] = useState<ResearchResult | null>(null)
  const [voice, setVoice] = useState('')
  const [platform, setPlatform] = useState('')

  // Don't auto-redirect once the wizard itself has created the tenant (the user is mid-flow). Only a
  // returning user who ALREADY had a tenant on arrival should be bounced to the dashboard.
  const startedRef = useRef(false)
  useEffect(() => {
    if (!isLoading && user?.tenant_id && !startedRef.current) {
      router.replace('/dashboard')
    }
  }, [isLoading, user, router])

  useEffect(() => {
    if (!slugEdited && orgName) setSlug(toSlug(orgName))
  }, [orgName, slugEdited])

  const canCreate = useMemo(() => orgName.trim().length >= 2 && slug.length >= 3, [orgName, slug])

  const createTenant = async () => {
    setCreating(true)
    setError('')
    try {
      const token = getToken()
      const res = await fetch('/api/auth/tenants/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ tenant_name: orgName.trim(), tenant_slug: slug, modules: ['chat'] }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Failed to create organization')
        return
      }
      startedRef.current = true
      if (data.access_token) updateSession(data.access_token, data.refresh_token)
      // Give the new tenant-scoped token a tick to propagate to the API client before the research step.
      setTimeout(() => setStep(1), 50)
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setCreating(false)
    }
  }

  const finish = async (save: boolean) => {
    setFinishing(true)
    try {
      // The org NAME is core (so the assistant says "BRCAStrong", not "[Organization Name]") — persist it
      // even on Skip. Voice + platform are saved only when the user fills them in and clicks Finish.
      if (save && voice.trim()) {
        await studioApi.createMemory(api, { kind: 'brand_voice', value: { descriptor: voice.trim() } })
      }
      const prof: { name?: string; default_platform?: string } = {}
      if (orgName.trim()) prof.name = orgName.trim()
      if (save && platform) prof.default_platform = platform
      if (Object.keys(prof).length) await studioApi.putProfile(api, prof)
      if (save && (voice.trim() || platform)) toast.success('Saved — your assistant is tuned to your voice.')
    } catch {
      toast.error("Couldn't save those — you can set them anytime in Studio.")
    } finally {
      setFinishing(false)
    }
    router.push('/dashboard')
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <LogoMark className="h-12 w-12 animate-pulse" glyphClassName="h-[50%] w-[50%]" />
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!user) return null

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-16 lg:py-12">
      <div className="reveal-stagger w-full max-w-2xl space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="font-display text-3xl font-semibold leading-tight tracking-tight text-foreground sm:text-4xl">
            Set up your <span className="text-gradient-warm">studio</span>
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            Name your org, then (optionally) let me learn it — so every post fits from day one.
          </p>
        </div>

        {/* Progress */}
        <div className="flex items-center justify-center gap-1">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center">
              <div className={cn(
                'flex items-center justify-center h-8 w-8 rounded-full text-xs font-medium transition-colors',
                i < step ? 'bg-primary text-primary-foreground'
                  : i === step ? 'bg-primary text-primary-foreground shadow-[0_4px_18px_-8px_var(--pau-glow-primary)]'
                    : 'bg-muted text-muted-foreground',
              )}>
                {i < step ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn('w-8 h-0.5 mx-1 transition-colors', i < step ? 'bg-primary' : 'bg-muted')} />
              )}
            </div>
          ))}
        </div>

        <Card>
          <CardHeader><CardTitle className="text-xl">{STEPS[step]}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {/* Step 0: Organization */}
            {step === 0 && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="org-name">Organization Name</Label>
                  <Input id="org-name" placeholder="Myra's Kids" value={orgName}
                    onChange={e => setOrgName(e.target.value)} autoFocus />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug">URL Slug</Label>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground whitespace-nowrap">org/</span>
                    <Input id="slug" placeholder="myras-kids" value={slug}
                      onChange={e => { setSlug(e.target.value); setSlugEdited(true) }} />
                  </div>
                  <p className="text-xs text-muted-foreground">Lowercase letters, numbers, and hyphens. Min 3 characters.</p>
                </div>
                {error && <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{error}</div>}
              </>
            )}

            {/* Step 1: Research (skippable) */}
            {step === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Point me at your website and I&apos;ll learn your mission, programs and audience — so every
                  suggestion fits. Totally optional; you can do this later in Studio.
                </p>
                <ResearchCard defaultName={orgName} onResult={(r) => { setResearch(r); if (r.one_liner && !voice) setVoice(r.one_liner) }} />
              </div>
            )}

            {/* Step 2: Voice & platform (skippable) */}
            {step === 2 && (
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="voice">Brand voice <span className="font-normal text-muted-foreground">(one line)</span></Label>
                  <Textarea id="voice" rows={2} value={voice} onChange={e => setVoice(e.target.value)}
                    placeholder="warm, hopeful, and grounded — speaks directly to families" className="resize-none text-sm" />
                  {research?.mission && (
                    <p className="text-xs text-muted-foreground">From your site: <span className="text-foreground/70">{research.mission}</span></p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Where do you mostly post?</Label>
                  <div className="flex flex-wrap gap-2">
                    {PLATFORMS.map(({ key, label, Icon }) => (
                      <button key={key} type="button" onClick={() => setPlatform(platform === key ? '' : key)}
                        className={cn('flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors',
                          platform === key ? 'border-primary bg-primary/10 text-foreground' : 'border-border text-muted-foreground hover:border-primary/50')}>
                        <Icon className="h-4 w-4" /> {label}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">Drafts will default to this platform. You can always pick another in chat.</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between">
          {step === 0 ? <span /> : (
            <Button variant="outline" onClick={() => setStep(s => s - 1)} disabled={creating || finishing}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
          )}

          {step === 0 && (
            <Button onClick={createTenant} disabled={!canCreate || creating}>
              {creating ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Creating…</> : <>Continue <ArrowRight className="h-4 w-4 ml-1" /></>}
            </Button>
          )}
          {step === 1 && (
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStep(2)}>Skip</Button>
              <Button onClick={() => setStep(2)}>Continue <ArrowRight className="h-4 w-4 ml-1" /></Button>
            </div>
          )}
          {step === 2 && (
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => finish(false)} disabled={finishing}>Skip</Button>
              <Button onClick={() => finish(true)} disabled={finishing}>
                {finishing ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Saving…</> : 'Finish'}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
