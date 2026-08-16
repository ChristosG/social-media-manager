export type Field = { key: string; label: string; placeholder?: string; textarea?: boolean }

export const FIELDS: Record<string, Field[]> = {
  platform: [
    { key: 'label', label: 'Display label', placeholder: 'TikTok' },
    { key: 'max_chars', label: 'Character limit', placeholder: '2200' },
    { key: 'tone', label: 'Tone', placeholder: 'fun, fast, trend-aware' },
    { key: 'hashtags', label: 'Hashtags', placeholder: '3-5' },
  ],
  content_type: [
    { key: 'description', label: 'Description', placeholder: 'Feature a volunteer and their impact.', textarea: true },
  ],
  research_source: [
    { key: 'type', label: 'Type', placeholder: 'rss | tavily | scrape' },
    { key: 'url', label: 'URL (if any)', placeholder: 'https://…/feed.xml' },
  ],
  skill_prompt: [
    { key: 'instruction', label: 'Instruction', placeholder: "End every post with 'Adopt, don't shop.'", textarea: true },
  ],
}

export function namePlaceholder(kind: string): string {
  return kind === 'platform' ? 'tiktok'
    : kind === 'content_type' ? 'Volunteer Spotlight'
    : kind === 'research_source' ? 'Newsletter RSS'
    : 'Always sign off'
}

export function buildConfig(kind: string, fields: Record<string, string>): Record<string, unknown> {
  const f: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(fields)) {
    if (v.trim()) f[k] = v.trim()
  }
  if (kind === 'platform' && typeof f.max_chars === 'string') {
    const n = parseInt(f.max_chars, 10)
    if (Number.isFinite(n)) f.max_chars = n; else delete f.max_chars
  }
  return f
}

/** Seed an editable string-field map from an existing capability config. */
export function configToFields(kind: string, config: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const f of FIELDS[kind] ?? []) {
    const v = config[f.key]
    if (v !== undefined && v !== null) out[f.key] = String(v)
  }
  return out
}

/** What each kind is for + how the agent uses it (section blurb). */
export const KIND_HELP: Record<string, string> = {
  platform: 'Channels the assistant can draft for. Each carries its own tone and length, applied automatically when you ask it to draft.',
  content_type: 'Reusable post formats. Mention one and the assistant follows that recipe.',
  research_source: 'Where the assistant pulls grounding from before it writes, so posts stay factual and on-topic.',
  skill_prompt: 'Standing instructions added to every turn — house rules the assistant always honors.',
}

/** A concise, per-row explanation of what a capability does + how to invoke it. */
export function describeCapability(kind: string, config: Record<string, unknown>): string {
  const str = (k: string) => {
    const v = config[k]
    return v === undefined || v === null ? '' : String(v)
  }
  if (kind === 'platform') {
    const tone = str('tone')
    const max = str('max_chars')
    const parts: string[] = []
    if (tone) parts.push(`tone: ${tone}`)
    if (max) parts.push(`up to ${max} chars`)
    const meta = parts.length ? ` (${parts.join(' · ')})` : ''
    const label = str('label') || ''
    return `Say "draft a ${label || 'post for this platform'}"${meta}.`
  }
  if (kind === 'content_type') {
    const desc = str('description')
    return desc || 'A reusable post format — mention it by name when you ask for a draft.'
  }
  if (kind === 'research_source') {
    const type = str('type')
    const url = str('url')
    if (type && url) return `${type} · ${url}`
    if (type) return `Source type: ${type}`
    if (url) return url
    return 'A place the assistant checks for grounding before writing.'
  }
  if (kind === 'skill_prompt') {
    const instruction = str('instruction')
    return instruction || 'A standing instruction applied to every message.'
  }
  return ''
}
