'use client'
import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'

export function VoiceCard({ title, description, value, onSave, saving }: {
  title: string; description: string; value: string; onSave: (v: string) => void; saving?: boolean
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <Card className="space-y-4 p-5">
      <div className="space-y-1">
        <h3 className="font-display text-base font-semibold tracking-tight text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
      <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3}
        placeholder="e.g. warm, grassroots, community-driven — avoid corporate jargon" />
      <div className="flex justify-end">
        <Button size="sm" disabled={saving || draft === value} onClick={() => onSave(draft)}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </Card>
  )
}
