'use client'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { ApiRequestError } from '@platform/auth-ui'
import { useResearchOrg } from '@/hooks/use-studio'
import type { ResearchResult } from '@/lib/studio-api'

export function ResearchCard({ defaultName = '', defaultUrl = '', onResult }: {
  defaultName?: string; defaultUrl?: string; onResult?: (r: ResearchResult) => void
} = {}) {
  const research = useResearchOrg()
  const [url, setUrl] = useState(defaultUrl)
  const [name, setName] = useState(defaultName)
  const [result, setResult] = useState<ResearchResult | null>(null)

  const run = async () => {
    try {
      const r = await research.mutateAsync({ website_url: url.trim(), org_name: name.trim() })
      setResult(r)
      onResult?.(r)
      toast.success('Learned your org — it now shapes every suggestion.')
    } catch (err) {
      // research_org commits your profile + programs in their own transactions BEFORE its slow web-fetch/
      // LLM tail, so a request timeout can surface as a 5xx even though your org info was already saved.
      // The hook refreshes Studio on settled either way — so tell the truth instead of "failed (admin only)".
      const status = err instanceof ApiRequestError ? err.status : 0
      if (status === 403) {
        toast.error('You need an admin or owner role to research your org.')
      } else if (status === 422) {
        toast.error((err instanceof ApiRequestError && err.message) || 'Check the website URL and try again.')
      } else if (status === 0 || status === 408 || status >= 500) {
        toast.info('Still working on this — it can take up to a minute. Your org details may already be saved; check Studio shortly.')
      } else {
        toast.error("Couldn't finish researching your org — please try again.")
      }
    }
  }

  return (
    <Card className="space-y-4 border-primary/30 bg-gradient-to-b from-primary/[0.06] to-transparent p-5 shadow-[0_8px_30px_-12px_var(--pau-glow-primary)]">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary ring-1 ring-inset ring-primary/20">
          <Sparkles className="h-5 w-5" />
        </span>
        <div className="space-y-1">
          <h3 className="font-display text-base font-semibold tracking-tight text-foreground">Learn about your org</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Point me at your website and I&apos;ll learn your mission and programs, so every suggestion
            actually fits. Takes ~20 seconds.
          </p>
        </div>
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Organization name" />
        <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="yourorg.org" />
      </div>
      <div className="flex justify-end">
        <Button size="sm" disabled={research.isPending || (!url.trim() && !name.trim())} onClick={run}>
          <Sparkles />
          {research.isPending ? 'Researching…' : 'Research my org'}
        </Button>
      </div>
      {result && (
        <div className="space-y-2.5 rounded-xl border border-sage/30 bg-sage/[0.08] p-4 text-sm">
          {result.mission && <p className="text-foreground"><span className="font-semibold text-sage">Mission</span> · {result.mission}</p>}
          {result.audience && (
            <p className="text-muted-foreground">
              <span className="font-semibold text-foreground">Audience</span> · {result.audience}
            </p>
          )}
          {result.programs?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {result.programs.map((p) => <Badge key={p.name} variant="success">{p.name}</Badge>)}
            </div>
          )}
          {result.sources?.length > 0 && (
            <p className="text-xs text-muted-foreground">Learned from {result.sources.length} source(s).</p>
          )}
        </div>
      )}
    </Card>
  )
}
