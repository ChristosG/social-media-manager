'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FileText, Loader2, RotateCcw, Save, Check, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { usePrompts, useSavePrompt, useResetPrompt } from '@/hooks/use-studio'
import type { PromptTemplate } from '@/lib/studio-api'

function PromptCard({ prompt }: { prompt: PromptTemplate }) {
  const save = useSavePrompt()
  const reset = useResetPrompt()
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(prompt.template)
  const [justSaved, setJustSaved] = useState(false)

  // Keep the editor in sync when the server copy changes (after save/reset/refetch).
  useEffect(() => { setValue(prompt.template) }, [prompt.template])

  const dirty = value.trim() !== prompt.template.trim()

  return (
    <div className="rounded-xl border border-border">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-panel/50">
        <ChevronRight className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{prompt.label}</span>
            {prompt.is_overridden
              ? <Badge variant="secondary" className="text-[10px]">customized</Badge>
              : <Badge variant="outline" className="text-[10px] text-muted-foreground">default</Badge>}
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{prompt.description}</p>
        </div>
        <code className="hidden shrink-0 rounded bg-panel/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">{prompt.key}</code>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border p-4">
          {prompt.placeholders.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Placeholders (kept as-is, filled in automatically):{' '}
              {prompt.placeholders.map((p) => (
                <code key={p} className="mr-1 rounded bg-panel/60 px-1 py-0.5 font-mono text-[11px] text-foreground/80">{p}</code>
              ))}
            </p>
          )}
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            spellCheck={false}
            className="min-h-[200px] w-full resize-y rounded-lg border border-border bg-background/60 p-3 font-mono text-[12px] leading-relaxed text-foreground/90 outline-none focus:border-primary/50"
          />
          <div className="flex items-center gap-2">
            <button
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate({ key: prompt.key, template: value }, {
                onSuccess: () => { setJustSaved(true); setTimeout(() => setJustSaved(false), 1500) },
              })}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-40"
            >
              {save.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : justSaved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
              {justSaved ? 'Saved' : 'Save'}
            </button>
            {prompt.is_overridden && (
              <button
                disabled={reset.isPending}
                onClick={() => reset.mutate(prompt.key)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Reset to default
              </button>
            )}
            {dirty && <span className="text-[11px] text-amber-400">unsaved changes</span>}
            <span className="ml-auto text-[11px] text-muted-foreground">applies on the next message</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function PromptsTab() {
  const { data, isLoading } = usePrompts()

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5" /> Prompts</CardTitle>
        <CardDescription>
          The exact instructions that drive the assistant. Ours are tuned, but you can tweak any of them —
          changes are per-organization and take effect on the next message. Reset to the built-in default anytime.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="py-8 text-center text-muted-foreground"><Loader2 className="inline h-5 w-5 animate-spin" /></div>
        ) : (
          <div className="space-y-2">
            {data?.prompts.map((p) => <PromptCard key={p.key} prompt={p} />)}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
