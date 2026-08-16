'use client'
import { useEffect, useState, useRef } from 'react'
import { getAccessToken } from '@platform/auth-ui'

/**
 * Fetches a URL with Authorization header and returns a blob URL.
 * Use for <img src>, <iframe src>, etc. where the browser can't send auth headers.
 */
export function useAuthBlobUrl(url: string | null): string | null {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const prevUrl = useRef<string | null>(null)

  useEffect(() => {
    if (!url) {
      setBlobUrl(null)
      return
    }

    // Avoid refetching the same URL
    if (url === prevUrl.current) return
    prevUrl.current = url

    let revoked = false
    const token = getAccessToken()
    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.blob()
      })
      .then(blob => {
        if (!revoked) {
          setBlobUrl(prev => {
            if (prev) URL.revokeObjectURL(prev)
            return URL.createObjectURL(blob)
          })
        }
      })
      .catch(() => {
        if (!revoked) setBlobUrl(null)
      })

    return () => {
      revoked = true
      setBlobUrl(prev => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
      prevUrl.current = null
    }
  }, [url])

  return blobUrl
}

/**
 * Fetch a resource with auth header. For imperative use (download buttons, text loading).
 */
export async function fetchWithAuth(url: string): Promise<Response> {
  const token = getAccessToken()
  return fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}
