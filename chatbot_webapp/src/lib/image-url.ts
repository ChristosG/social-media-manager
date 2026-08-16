// Allowlist image URLs before putting them in <img src>/<a href>. The ss-gallery block bypasses
// react-markdown's urlTransform, so a prompt-injected agent could otherwise emit a javascript:
// URL that becomes a clickable XSS link. Permit only http(s), data:image/*, and our own signed
// served images (relative /api/v1/img/...).
export function isSafeImageUrl(u: unknown): u is string {
  if (typeof u !== 'string') return false
  return (
    /^https?:\/\//i.test(u) ||
    /^data:image\/(png|jpe?g|webp|gif|avif|bmp);base64,/i.test(u) ||
    u.startsWith('/api/v1/img/')
  )
}

// Allowlist link hrefs (e.g. citation chips). Citation URLs can originate from external grounding
// (web-search / scraped sources), so an attacker-influenced value must never become a javascript:/data:
// link that executes on click. Permit only http(s) and mailto:.
export function isSafeHref(u: unknown): u is string {
  return typeof u === 'string' && (/^https?:\/\//i.test(u) || /^mailto:/i.test(u))
}

// Max-quality download: force attachment for our served images; data: URLs rely on the download attr.
export function toDownloadUrl(u: string): string {
  if (u.startsWith('/api/v1/img/')) return u + (u.includes('?') ? '&' : '?') + 'dl=1'
  return u
}

export function triggerDownload(url: string, filename: string): void {
  const a = document.createElement('a')
  a.href = toDownloadUrl(url)
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}
