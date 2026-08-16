'use client'
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { useUpdateCapability, useCreateCapability } from '@/hooks/use-studio'
import { FIELDS, buildConfig, configToFields } from './capability-fields'
import type { Capability } from '@/lib/studio-api'

export function EditCapabilityDialog({ capability, open, onOpenChange }: {
  capability: Capability; open: boolean; onOpenChange: (open: boolean) => void
}) {
  const update = useUpdateCapability()
  const create = useCreateCapability()
  const [name, setName] = useState(capability.name)
  const [fields, setFields] = useState<Record<string, string>>(() => configToFields(capability.kind, capability.config))
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setFields((f) => ({ ...f, [k]: e.target.value }))

  // A global is read-only; "editing" it means creating an org override that shadows it (same kind + name).
  const isOverride = capability.is_global
  const pending = update.isPending || create.isPending

  const submit = async () => {
    if (!name.trim()) return
    const config = buildConfig(capability.kind, fields)
    try {
      if (isOverride) {
        await create.mutateAsync({ kind: capability.kind, name: name.trim(), config })
        toast.success('Saved as your override')
      } else {
        await update.mutateAsync({ id: capability.id, name: name.trim(), config })
        toast.success('Saved')
      }
      onOpenChange(false)
    } catch {
      toast.error('Save failed — you may need an admin role.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isOverride ? 'Override default' : 'Edit'}</DialogTitle>
          <DialogDescription>
            {isOverride
              ? 'Defaults are read-only. Saving creates your own version that shadows the default — effective on the next message.'
              : 'Changes take effect on the next message.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={isOverride} />
          </div>
          {(FIELDS[capability.kind] ?? []).map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label>{f.label}</Label>
              {f.textarea
                ? <Textarea value={fields[f.key] ?? ''} onChange={set(f.key)} placeholder={f.placeholder} rows={3} />
                : <Input value={fields[f.key] ?? ''} onChange={set(f.key)} placeholder={f.placeholder} />}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button disabled={!name.trim() || pending} onClick={submit}>
            {pending ? 'Saving…' : isOverride ? 'Create override' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
