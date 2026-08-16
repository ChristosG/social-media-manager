'use client'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Layers, Pencil, Trash2, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import { usePrograms, useCreateProgram, useUpdateProgram, useDeleteProgram } from '@/hooks/use-studio'
import type { Program } from '@/lib/studio-api'

function ProgramRow({ program }: { program: Program }) {
  const update = useUpdateProgram()
  const del = useDeleteProgram()
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [name, setName] = useState(program.name)
  const [description, setDescription] = useState(program.description ?? '')

  const save = async () => {
    if (!name.trim()) return
    try {
      await update.mutateAsync({ id: program.id, name: name.trim(), description: description.trim() })
      toast.success('Program saved')
      setEditing(false)
    } catch {
      toast.error('Save failed')
    }
  }
  const remove = async () => {
    try {
      await del.mutateAsync(program.id)
      toast.success('Program removed')
    } catch {
      toast.error('Remove failed')
    } finally {
      setConfirm(false)
    }
  }

  if (editing) {
    return (
      <div className="space-y-2.5 rounded-xl border border-border bg-muted/30 p-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Program name" />
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
          placeholder="What this program does." />
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" disabled={update.isPending}
            onClick={() => { setName(program.name); setDescription(program.description ?? ''); setEditing(false) }}>
            Cancel
          </Button>
          <Button size="sm" disabled={update.isPending || !name.trim()} onClick={save}>
            {update.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-accent">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-foreground">{program.name}</div>
        {program.description && (
          <p className="mt-0.5 text-sm text-muted-foreground leading-relaxed">{program.description}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button size="icon-sm" variant="ghost" onClick={() => setEditing(true)} aria-label={`Edit ${program.name}`}
          className="text-muted-foreground hover:text-foreground">
          <Pencil className="h-4 w-4" />
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={() => setConfirm(true)} aria-label={`Delete ${program.name}`}
          className="text-muted-foreground hover:text-destructive">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Delete program?"
        description={`"${program.name}" will be removed from what the assistant knows.`}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
        onCancel={() => setConfirm(false)}
      />
    </div>
  )
}

export function ProgramsCard() {
  const { data, isLoading } = usePrograms()
  const create = useCreateProgram()
  const programs = data?.programs ?? []

  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const add = async () => {
    if (!name.trim()) return
    try {
      await create.mutateAsync({ name: name.trim(), description: description.trim() || undefined })
      toast.success('Program added')
      setName(''); setDescription(''); setAdding(false)
    } catch {
      toast.error('Add failed')
    }
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary ring-1 ring-inset ring-primary/20">
            <Layers className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <h3 className="font-display text-base font-semibold tracking-tight text-foreground">Programs</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              The work your org does. The assistant draws on these to ground every suggestion.
            </p>
          </div>
        </div>
        {!adding && (
          <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus />Add program
          </Button>
        )}
      </div>

      {adding && (
        <div className="space-y-2.5 rounded-xl border border-border bg-muted/30 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">New program</span>
            <Button size="icon-sm" variant="ghost" onClick={() => { setName(''); setDescription(''); setAdding(false) }}
              aria-label="Cancel" className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Program name" />
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
            placeholder="What this program does." />
          <div className="flex justify-end">
            <Button size="sm" disabled={create.isPending || !name.trim()} onClick={add}>
              {create.isPending ? 'Adding…' : 'Add'}
            </Button>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && programs.length === 0 && !adding && (
          <p className="text-sm text-muted-foreground">No programs yet. Add one, or run research to learn them automatically.</p>
        )}
        {programs.map((p) => <ProgramRow key={p.id} program={p} />)}
      </div>
    </Card>
  )
}
