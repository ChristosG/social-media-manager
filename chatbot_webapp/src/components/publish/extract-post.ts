/**
 * Pure helper: extract caption + image list from an assistant message's markdown.
 *
 * Image sources are detected in two places:
 *  1. Standard markdown image syntax  ![alt](url)
 *  2. ```ss-gallery``` fenced blocks   (one URL per line — the ImageCarousel format)
 *
 * Safe image URLs begin with:
 *  - /api/v1/img/{uuid}?...   (our signed served images)
 *  - https?://               (external absolute URLs)
 *  - data:image/...          (inline base64 — id derived from a hash suffix)
 *
 * The uuid is extracted from the /api/v1/img/{uuid} path segment.
 * For external URLs the full URL is used as the id (stable enough for dedup).
 */

export interface ExtractedPost {
  caption: string
  images: { id: string; url: string }[]
}

/** Extract the image id from a URL. */
function imageId(url: string): string {
  // /api/v1/img/<uuid>  — capture the uuid segment before any query string
  const m = url.match(/\/img\/([0-9a-f-]{36})/i)
  if (m) return m[1]
  // Fallback: use the whole URL (external images, data: URIs)
  return url
}

/** True for URLs we recognise as agent-generated images. */
function isAgentImageUrl(url: string): boolean {
  return (
    url.startsWith('/api/v1/img/') ||
    /^https?:\/\//i.test(url) ||
    /^data:image\/(png|jpe?g|webp|gif|avif|bmp);base64,/i.test(url)
  )
}

export function extractPost(markdown: string): ExtractedPost {
  const images: { id: string; url: string }[] = []
  const seenIds = new Set<string>()

  function addImage(url: string) {
    if (!isAgentImageUrl(url)) return
    const id = imageId(url)
    if (seenIds.has(id)) return
    seenIds.add(id)
    images.push({ id, url })
  }

  // ── 1. Strip ss-gallery fenced blocks, harvesting URLs ──────────────────────
  let text = markdown.replace(
    /```ss-gallery\n([\s\S]*?)```/g,
    (_match, body: string) => {
      body
        .trim()
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
        .forEach(addImage)
      return '' // remove the block from caption
    },
  )

  // ── 2. Strip standard markdown images ![alt](url), harvesting URLs ──────────
  text = text.replace(/!\[[^\]]*\]\(([^)]+)\)/g, (_match, url: string) => {
    addImage(url.trim())
    return '' // remove from caption
  })

  // ── 3. Collapse blank lines left by the removals ────────────────────────────
  const caption = text
    .replace(/\n{3,}/g, '\n\n') // max 2 consecutive newlines
    .trim()

  return { caption, images }
}
