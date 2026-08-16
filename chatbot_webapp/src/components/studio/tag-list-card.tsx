'use client'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { X } from 'lucide-react'

export function TagListCard({ title, description, items, onAdd, onRemove }: {
  title: string; description: string
  items: { id: string; label: string }[]
  onAdd: (label: string) => void; onRemove: (id: string) => void
}) {
  const [text, setText] = useState('')
  return (
    <Card className="space-y-4 p-5">
      <div className="space-y-1">
        <h3 className="font-display text-base font-semibold tracking-tight text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.length === 0 && <span className="text-sm text-muted-foreground">None yet.</span>}
        {items.map((it) => (
          <Badge key={it.id} variant="coral" className="gap-1 pr-1.5">
            {it.label}
            <button
              onClick={() => onRemove(it.id)}
              aria-label={`Remove ${it.label}`}
              className="grid h-4 w-4 place-items-center rounded-full text-primary/70 transition-colors hover:bg-primary/20 hover:text-primary"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Add and press Enter"
          onKeyDown={(e) => { if (e.key === 'Enter' && text.trim()) { onAdd(text.trim()); setText('') } }} />
        <Button size="sm" variant="outline" disabled={!text.trim()} onClick={() => { onAdd(text.trim()); setText('') }}>Add</Button>
      </div>
    </Card>
  )
}
