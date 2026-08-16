'use client'

import { memo, useState, useMemo } from 'react'
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import 'highlight.js/styles/github-dark.css'
import { icons } from '@/components/icons'
import { ImageCarousel } from './image-carousel'
import { isSafeImageUrl, toDownloadUrl } from '@/lib/image-url'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('go', go)
hljs.registerLanguage('java', java)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('json', json)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('css', css)

interface MarkdownRendererProps {
  content: string
}

function CodeBlock({ className, children }: { className?: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  const highlighted = useMemo(() => {
    if (language && hljs.getLanguage(language)) {
      try {
        return hljs.highlight(code, { language }).value
      } catch {}
    }
    return null
  }, [code, language])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="group/code relative my-3 rounded-xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-muted px-3 py-1.5">
        <span className="text-xs text-muted-foreground font-mono">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Copy code"
        >
          {copied ? (
            <><icons.check className="h-3 w-3" /> Copied</>
          ) : (
            <><icons.copy className="h-3 w-3" /> Copy</>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs bg-card">
        {highlighted ? (
          <code className="hljs font-mono" dangerouslySetInnerHTML={{ __html: highlighted }} />
        ) : (
          <code className="font-mono">{code}</code>
        )}
      </pre>
    </div>
  )
}

const plugins = [remarkGfm]

const mdComponents = {
  pre: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) => {
    // Generated image variations arrive as a ```ss-gallery``` block (one URL per line).
    if ((className || '').includes('language-ss-gallery')) {
      const urls = String(children).trim().split('\n').map((s) => s.trim()).filter(isSafeImageUrl)
      return <ImageCarousel urls={urls} />
    }
    const isBlock = !!className || String(children).includes('\n')
    if (isBlock) {
      return <CodeBlock className={className}>{children}</CodeBlock>
    }
    return (
      <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono break-words">
        {children}
      </code>
    )
  },
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="border border-border px-3 py-1.5 text-left font-medium bg-muted">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border border-border px-3 py-1.5">{children}</td>
  ),
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline hover:opacity-80">
      {children}
    </a>
  ),
  img: ({ src, alt }: { src?: string | Blob; alt?: string }) => {
    // Allowlist the URL (no javascript:/data:text), then render with a hover download overlay.
    if (!isSafeImageUrl(src)) return null
    return (
      <span className="group relative my-3 block w-full max-w-md">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt || 'Generated image'} loading="lazy" className="w-full rounded-xl border border-border" />
        <a
          href={toDownloadUrl(src)}
          download="image.png"
          className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full bg-black/60 text-white opacity-0 backdrop-blur-sm transition hover:bg-black/80 group-hover:opacity-100"
          aria-label="Download image"
        >
          <icons.download className="h-4 w-4" />
        </a>
      </span>
    )
  },
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>,
  p: ({ children }: { children?: React.ReactNode }) => <p className="my-1.5 leading-relaxed break-words [overflow-wrap:anywhere]">{children}</p>,
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-2 border-l-2 border-primary pl-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="font-display text-xl font-semibold tracking-tight mt-4 mb-2">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="font-display text-lg font-semibold tracking-tight mt-3 mb-2">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="font-display text-base font-semibold tracking-tight mt-3 mb-1">{children}</h3>,
  hr: () => <hr className="my-4 border-border" />,
}

export const MarkdownRenderer = memo(function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null

  return (
    <ReactMarkdown
      remarkPlugins={plugins}
      components={mdComponents}
      // Allow our own generated images (data: URLs); keep the safe default for everything else.
      urlTransform={(url) => (url.startsWith('data:image/') ? url : defaultUrlTransform(url))}
    >
      {content}
    </ReactMarkdown>
  )
})
