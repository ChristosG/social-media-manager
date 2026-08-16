'use client'
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { useCreateCapability } from '@/hooks/use-studio'
import { FIELDS, namePlaceholder, buildConfig } from './capability-fields'

export function AddCapabilityDialog({ kind, title }: { kind: string; title: string }) {
  const create = useCreateCapability()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [fields, setFields] = useState<Record<string, string>>({})
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setFields((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    if (!name.trim()) return
    try {
      await create.mutateAsync({ kind, name: name.trim(), config: buildConfig(kind, fields) })
      toast.success(`Added to ${title}`)
      setOpen(false); setName(''); setFields({})
    } catch {
      toast.error('Add failed — you may need an admin role.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline"><Plus />Add</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add {title.replace(/s$/, '')}</DialogTitle>
          <DialogDescription>Available on the next message. Disable or remove it any time.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={namePlaceholder(kind)} />
          </div>
          {(FIELDS[kind] ?? []).map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label>{f.label}</Label>
              {f.textarea
                ? <Textarea value={fields[f.key] ?? ''} onChange={set(f.key)} placeholder={f.placeholder} rows={3} />
                : <Input value={fields[f.key] ?? ''} onChange={set(f.key)} placeholder={f.placeholder} />}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button disabled={!name.trim() || create.isPending} onClick={submit}>
            {create.isPending ? 'Adding…' : 'Add'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
