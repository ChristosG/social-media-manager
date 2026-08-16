let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function clearAccessToken(): void {
  accessToken = null
}

export function getTokenExpiry(jwt: string): number | null {
  try {
    const parts = jwt.split('.')
    if (parts.length !== 3) return null

    // Base64url decode the payload
    const payload = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/')

    const decoded = typeof atob !== 'undefined'
      ? atob(payload)
      : Buffer.from(payload, 'base64').toString('utf-8')

    const parsed = JSON.parse(decoded)
    return typeof parsed.exp === 'number' ? parsed.exp : null
  } catch {
    return null
  }
}

export function getSecondsUntilExpiry(jwt: string): number | null {
  const exp = getTokenExpiry(jwt)
  if (exp === null) return null
  return exp - Math.floor(Date.now() / 1000)
}

export interface JwtClaims {
  tid?: string
  roles?: string[]
  permissions?: string[]
  custom?: Record<string, string>
}

export function parseJwtClaims(jwt: string): JwtClaims | null {
  try {
    const parts = jwt.split('.')
    if (parts.length !== 3) return null

    const payload = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/')

    const decoded = typeof atob !== 'undefined'
      ? atob(payload)
      : Buffer.from(payload, 'base64').toString('utf-8')

    const parsed = JSON.parse(decoded)
    return {
      tid: parsed.tid ?? undefined,
      roles: Array.isArray(parsed.roles) ? parsed.roles : undefined,
      permissions: Array.isArray(parsed.permissions) ? parsed.permissions : undefined,
      custom: parsed.custom && typeof parsed.custom === 'object' ? parsed.custom : undefined,
    }
  } catch {
    return null
  }
}
