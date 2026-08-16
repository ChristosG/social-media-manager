'use client'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useCapabilities, useUpdateCapability, useDeleteCapability } from '@/hooks/use-studio'
import type { Capability } from '@/lib/studio-api'
import { AddCapabilityDialog } from './add-capability-dialog'
import { EditCapabilityDialog } from './edit-capability-dialog'
import { KIND_HELP, describeCapability } from './capability-fields'

const KINDS: { kind: string; title: string }[] = [
  { kind: 'platform', title: 'Platforms' },
  { kind: 'content_type', title: 'Content types' },
  { kind: 'research_source', title: 'Research sources' },
  { kind: 'skill_prompt', title: 'Skills' },
]

export function CapabilitiesTab() {
  const { data, isLoading } = useCapabilities()
  const update = useUpdateCapability()
  const del = useDeleteCapability()
  const caps = data?.capabilities ?? []
  const [editing, setEditing] = useState<Capability | null>(null)

  const toggle = async (c: Capability) => {
    try { await update.mutateAsync({ id: c.id, enabled: !c.enabled }); toast.success(c.enabled ? 'Disabled' : 'Enabled') }
    catch { toast.error('Update failed — admin role required.') }
  }
  const remove = async (c: Capability) => {
    try { await del.mutateAsync(c.id); toast.success('Removed') }
    catch { toast.error('Remove failed — admin role required.') }
  }

  return (
    <div className="space-y-4 reveal-stagger">
      <p className="text-sm text-muted-foreground leading-relaxed">
        What the assistant can do. Defaults apply to everyone; add your own or disable a default — changes take effect on the next message.
      </p>
      {KINDS.map(({ kind, title }) => {
        const items = caps.filter((c) => c.kind === kind)
        return (
          <Card key={kind} className="space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <h3 className="font-display text-base font-semibold tracking-tight text-foreground">{title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{KIND_HELP[kind]}</p>
              </div>
              <AddCapabilityDialog kind={kind} title={title} />
            </div>
            <div className="space-y-1">
              {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {!isLoading && items.length === 0 && <p className="text-sm text-muted-foreground">None yet.</p>}
              {items.map((c) => (
                <div
                  key={c.id}
                  className={cn(
                    'rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-accent',
                    !c.enabled && 'opacity-60',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{String(c.config.label ?? c.name)}</span>
                      <Badge variant={c.is_global ? 'muted' : 'coral'}>{c.is_global ? 'Default' : 'Custom'}</Badge>
                      {!c.enabled && <Badge variant="outline" className="text-muted-foreground">Off</Badge>}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <Button size="icon-sm" variant="ghost" onClick={() => setEditing(c)}
                        aria-label={c.is_global ? `Override ${c.name}` : `Edit ${c.name}`}
                        className="text-muted-foreground hover:text-foreground">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {c.is_global ? (
                        <span className="text-xs text-muted-foreground">Default</span>
                      ) : (
                        <>
                          <Switch checked={c.enabled} onCheckedChange={() => toggle(c)} aria-label={`Toggle ${c.name}`} />
                          <Button size="icon-sm" variant="ghost" onClick={() => remove(c)} aria-label={`Delete ${c.name}`}
                            className="text-muted-foreground hover:text-destructive">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground" title={describeCapability(c.kind, c.config)}>
                    {describeCapability(c.kind, c.config)}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        )
      })}
      {editing && (
        <EditCapabilityDialog
          key={editing.id}
          capability={editing}
          open={!!editing}
          onOpenChange={(o) => { if (!o) setEditing(null) }}
        />
      )}
    </div>
  )
}
