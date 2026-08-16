'use client'
import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Building2, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { useProfile, useUpdateProfile } from '@/hooks/use-studio'

export function ProfileCard() {
  const { data } = useProfile()
  const update = useUpdateProfile()
  const profile = data?.profile

  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [mission, setMission] = useState('')
  const [oneLiner, setOneLiner] = useState('')
  const [audience, setAudience] = useState('')
  const [regions, setRegions] = useState('')

  // Re-seed the draft from the persisted profile whenever it changes (and we're not mid-edit).
  useEffect(() => {
    if (editing) return
    setName(profile?.name ?? '')
    setMission(profile?.mission ?? '')
    setOneLiner(profile?.one_liner ?? '')
    setAudience(profile?.audience ?? '')
    setRegions((profile?.regions ?? []).join(', '))
  }, [profile, editing])

  const save = async () => {
    try {
      await update.mutateAsync({
        name: name.trim(),
        mission: mission.trim(),
        one_liner: oneLiner.trim(),
        audience: audience.trim(),
        regions: regions.split(',').map((r) => r.trim()).filter(Boolean),
      })
      toast.success('Organization profile saved')
      setEditing(false)
    } catch {
      toast.error('Save failed')
    }
  }

  const hasAny = Boolean(profile?.name || profile?.mission || profile?.one_liner || profile?.audience || (profile?.regions?.length ?? 0) > 0)

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary ring-1 ring-inset ring-primary/20">
            <Building2 className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <h3 className="font-display text-base font-semibold tracking-tight text-foreground">Organization profile</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              What the assistant knows about your org. This persists and shapes every suggestion.
            </p>
          </div>
        </div>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            <Pencil />Edit
          </Button>
        )}
      </div>

      {editing ? (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Your organization's name (how the assistant should refer to you)" />
          </div>
          <div className="space-y-1.5">
            <Label>Mission</Label>
            <Textarea value={mission} onChange={(e) => setMission(e.target.value)} rows={3}
              placeholder="What your organization sets out to do." />
          </div>
          <div className="space-y-1.5">
            <Label>One-liner</Label>
            <Input value={oneLiner} onChange={(e) => setOneLiner(e.target.value)}
              placeholder="A short, punchy summary of your org." />
          </div>
          <div className="space-y-1.5">
            <Label>Audience</Label>
            <Input value={audience} onChange={(e) => setAudience(e.target.value)}
              placeholder="Who you're speaking to — donors, volunteers, families…" />
          </div>
          <div className="space-y-1.5">
            <Label>Regions</Label>
            <Input value={regions} onChange={(e) => setRegions(e.target.value)}
              placeholder="Comma-separated, e.g. Athens, Thessaloniki" />
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" disabled={update.isPending} onClick={() => setEditing(false)}>Cancel</Button>
            <Button size="sm" disabled={update.isPending} onClick={save}>
              {update.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3 text-sm">
          {!hasAny && (
            <p className="text-muted-foreground">
              Nothing saved yet. Run research above, or add it manually with Edit.
            </p>
          )}
          {profile?.name && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Name</div>
              <p className="mt-0.5 text-foreground leading-relaxed">{profile.name}</p>
            </div>
          )}
          {profile?.mission && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Mission</div>
              <p className="mt-0.5 text-foreground leading-relaxed">{profile.mission}</p>
            </div>
          )}
          {profile?.one_liner && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">One-liner</div>
              <p className="mt-0.5 text-foreground leading-relaxed">{profile.one_liner}</p>
            </div>
          )}
          {profile?.audience && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Audience</div>
              <p className="mt-0.5 text-foreground leading-relaxed">{profile.audience}</p>
            </div>
          )}
          {(profile?.regions?.length ?? 0) > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Regions</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {profile!.regions.map((r) => <Badge key={r} variant="muted">{r}</Badge>)}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
